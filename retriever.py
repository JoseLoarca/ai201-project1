"""
retriever.py — Query understanding and chunk retrieval.

Responsibilities:
- Classify the user's question into a structured intent object using
  pure Python keyword matching (sources, course_code, needs_professor_filter)
- Translate that intent into ChromaDB metadata filters
- For professor-based questions, look up which professors are relevant for
  the queried course, then retrieve top-k chunks per professor to avoid
  one professor's volume dominating the results
- For all other questions, run a standard top-k similarity search with filters

Functions intended for external use:
    retrieve(query) -> list[dict]   Main entry point. Returns retrieved chunks.
"""

import re
from typing import Optional

from embedder import CHROMA_COLLECTION_NAME, _get_chroma_client, _get_embedding_model
from logger import get_session_logger

logger = get_session_logger()

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

TOP_K = 3

# Valid source values as stored in ChromaDB metadata
VALID_SOURCES = {
    "ratemyprofessor",
    "reddit",
    "uopeople_course_list",
    "uopeople_catalog",
}

# ---------------------------------------------------------------------------
# Intent classification — pure Python keyword matching
# ---------------------------------------------------------------------------

# Keywords that suggest the query is about professor reviews / ratings
_PROFESSOR_KEYWORDS = {
    "professor", "instructor", "teacher", "prof", "teaches", "taught",
    "feedback", "grading", "grader", "rating", "review", "rated",
}

# Keywords that suggest student experience: difficulty, tips, opinions
_REDDIT_KEYWORDS = {
    "difficult", "hard", "easy", "struggle", "tips", "advice", "recommend",
    "experience", "opinion", "worth", "workload", "pass", "fail", "study",
    "anyone", "students", "people", "community",
}

# Keywords that suggest official course info: descriptions, prerequisites
_COURSE_LIST_KEYWORDS = {
    "about", "description", "cover", "covers", "topic", "learn", "teaches",
    "prerequisite", "credit", "credits", "what is", "syllabus",
    "course", "courses", "class", "classes", "subject", "subjects",
}

# Keywords that suggest degree-level info: pathways, requirements
_CATALOG_KEYWORDS = {
    "degree", "program", "requirement", "pathway", "major", "curriculum",
    "bachelor", "bs", "bscs", "graduation", "complete",
}


def determine_question_intent(query: str) -> dict:
    """
    Classify the user's query into a structured intent object using keyword
    matching. No external model calls required.

    Returns a dict with:
        sources (list[str])         — which collections to search
        course_code (str)           — e.g. "CS2204", or "" if none found
        needs_professor_filter (bool)
    """
    q = query.lower()
    tokens = set(re.findall(r"\b\w+\b", q))

    # --- Course code extraction (always reliable via regex) ---
    code_match = re.search(r"\bcs\s*(\d{4})\b", q)
    course_code = f"CS{code_match.group(1)}" if code_match else ""

    # --- Source selection ---
    sources = []

    if tokens & _PROFESSOR_KEYWORDS:
        sources.append("ratemyprofessor")
    if tokens & _REDDIT_KEYWORDS:
        sources.append("reddit")
        # Reddit often has professor opinions too
        if "ratemyprofessor" not in sources and tokens & _PROFESSOR_KEYWORDS:
            sources.append("ratemyprofessor")
    if tokens & _COURSE_LIST_KEYWORDS or course_code:
        sources.append("uopeople_course_list")
    if tokens & _CATALOG_KEYWORDS:
        sources.append("uopeople_catalog")

    # Default: search everything when no signals are strong enough
    if not sources:
        sources = list(VALID_SOURCES)

    # Deduplicate while preserving order
    seen = set()
    sources = [s for s in sources if not (s in seen or seen.add(s))]

    # --- Professor filter ---
    # Only meaningful when asking about professors for a specific course
    # (used to trigger the per-professor retrieval loop that avoids volume bias).
    # General professor questions ("who gives good feedback?") don't need it —
    # semantic similarity handles those fine without per-professor looping.
    has_professor_signal = bool(tokens & _PROFESSOR_KEYWORDS)
    needs_professor_filter = has_professor_signal and bool(course_code)

    result = {
        "sources": sources,
        "course_code": course_code,
        "needs_professor_filter": needs_professor_filter,
    }
    logger.info(f"Query intent: {result}")
    return result


# ---------------------------------------------------------------------------
# ChromaDB filter builder
# ---------------------------------------------------------------------------

def _build_where_filter(sources: list[str]) -> Optional[dict]:
    """
    Build a ChromaDB `where` filter that restricts results to the given sources.

    Course code filtering is intentionally omitted — the embedding similarity
    of the query already surfaces course-relevant chunks naturally, and
    metadata-based course_code filtering caused more problems than it solved
    (multi-course Reddit chunks have course_code="" and would be excluded,
    catalog chunks rarely have course_code set, etc.).

    ChromaDB filter syntax:
    - Single source:    {"source": {"$eq": "value"}}
    - Multiple sources: {"source": {"$in": [...]}}
    """
    if not sources or len(sources) == len(VALID_SOURCES):
        return None
    if len(sources) == 1:
        return {"source": {"$eq": sources[0]}}
    return {"source": {"$in": sources}}


# ---------------------------------------------------------------------------
# Professor lookup
# ---------------------------------------------------------------------------

def get_professors_for_course(course_code: str) -> list[str]:
    """
    Query ChromaDB for all distinct professor names that have reviewed
    a specific course. Used to set up per-professor retrieval loops.

    Args:
        course_code: normalized course code e.g. "CS2204"

    Returns:
        Sorted list of unique professor names found in RMP reviews for
        that course. Empty list if none found.
    """
    client = _get_chroma_client()
    collection = client.get_or_create_collection(name=CHROMA_COLLECTION_NAME)

    where_filter = {
        "$and": [
            {"source": {"$eq": "ratemyprofessor"}},
            {"course_code": {"$eq": course_code}},
        ]
    }

    try:
        results = collection.get(where=where_filter, include=["metadatas"])
        names = {
            m["professor_name"]
            for m in results["metadatas"]
            if m.get("professor_name")
        }
        professors = sorted(names)
        logger.info(f"Professors found for {course_code}: {professors}")
        return professors
    except Exception as e:
        logger.warning(f"Professor lookup failed for {course_code}: {e}")
        return []


# ---------------------------------------------------------------------------
# Core retrieval
# ---------------------------------------------------------------------------

def _query_collection(
    query_embedding: list[float],
    where_filter: Optional[dict],
    n_results: int,
) -> list[dict]:
    """
    Run a similarity search against ChromaDB and return a flat list of
    result dicts, each with keys: text, metadata, distance.
    """
    client = _get_chroma_client()
    collection = client.get_or_create_collection(name=CHROMA_COLLECTION_NAME)

    kwargs = {
        "query_embeddings": [query_embedding],
        "n_results": n_results,
        "include": ["documents", "metadatas", "distances"],
    }
    if where_filter:
        kwargs["where"] = where_filter

    try:
        results = collection.query(**kwargs)
    except Exception as e:
        logger.warning(f"ChromaDB query failed: {e}")
        return []

    chunks = []
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        chunks.append({"text": doc, "metadata": meta, "distance": dist})

    return chunks


def _rerank_by_course_code(chunks: list[dict], course_code: str) -> list[dict]:
    """
    Stable rerank: chunks whose text mentions the course code float to the
    front; the rest follow in their original (distance-sorted) order.

    This is a lightweight post-retrieval fix for queries like
    "tips for passing CS1102" where dense retrieval surfaces semantically
    similar but course-agnostic chunks above the course-specific one.
    """
    # Match "CS1102", "CS 1102", "cs1102" etc.
    pattern = re.compile(
        r"\b" + re.escape(course_code[:2]) + r"\s*" + re.escape(course_code[2:]) + r"\b",
        re.IGNORECASE,
    )
    mentioned = [c for c in chunks if pattern.search(c["text"])]
    not_mentioned = [c for c in chunks if not pattern.search(c["text"])]

    if mentioned:
        logger.debug(
            f"Reranked {len(mentioned)} chunk(s) mentioning {course_code} to front."
        )

    return mentioned + not_mentioned


def retrieve(query: str) -> list[dict]:
    """
    Main retrieval entry point.

    Pipeline:
        1. Classify the query intent with Gemma 4
        2. Embed the query with all-MiniLM-L6-v2
        3a. If needs_professor_filter=True:
              Look up relevant professors → retrieve top-k per professor
        3b. Otherwise:
              Single similarity search with source + course_code filters
        4. Return the combined list of retrieved chunks

    Args:
        query: raw user question string

    Returns:
        List of dicts with keys: text (str), metadata (dict), distance (float).
        Lower distance = more similar (cosine distance, range 0–2).
    """
    logger.info(f"Retrieving for query: '{query}'")

    intent = determine_question_intent(query)
    sources = intent["sources"]
    course_code = intent["course_code"]
    needs_professor_filter = intent["needs_professor_filter"]

    model = _get_embedding_model()
    query_embedding = model.encode(query, convert_to_list=True)

    # --- Professor-filtered path ---
    # Only enter this path when a course_code is present. Without one there's
    # no meaningful way to look up professors — the per-professor loop exists
    # specifically to avoid volume bias when asking about professors for a
    # given course. For general professor questions (e.g. "who gives good
    # feedback?") the standard semantic search on ratemyprofessor is correct.
    if needs_professor_filter and course_code:
        professors = get_professors_for_course(course_code)

        if not professors:
            logger.info(f"No professors found for {course_code}; falling back to standard RMP search.")
            return _query_collection(query_embedding, _build_where_filter(["ratemyprofessor"]), TOP_K)

        # Retrieve top-k per professor to avoid volume bias
        all_chunks = []
        for professor in professors:
            where_filter = {
                "$and": [
                    {"source": {"$eq": "ratemyprofessor"}},
                    {"professor_name": {"$eq": professor}},
                ]
            }
            chunks = _query_collection(query_embedding, where_filter, TOP_K)
            logger.info(f"  {professor}: {len(chunks)} chunks retrieved")
            all_chunks.extend(chunks)

        # Sort combined results by distance (ascending = most similar first)
        all_chunks.sort(key=lambda c: c["distance"])
        return all_chunks

    # --- Standard path ---
    # Source filtering narrows the search to relevant collections.
    # Course code filtering is dropped for most sources — semantic similarity
    # handles it. The one exception is uopeople_course_list: it has exactly
    # 1 chunk per course with a reliable course_code field, so without a filter
    # the query "What is CS4407 about?" returns unrelated course descriptions
    # instead of the CS4407 entry.
    #
    # When course_code is present and uopeople_course_list is a requested source,
    # run it as a separate filtered query and merge with the rest.

    other_sources = [s for s in sources if s != "uopeople_course_list"]
    all_chunks: list[dict] = []

    if other_sources:
        all_chunks.extend(
            _query_collection(query_embedding, _build_where_filter(other_sources), TOP_K)
        )

    # When a specific course code is requested, also pull reddit chunks whose
    # metadata course_code matches directly. These per-course blocks (e.g. a
    # single "- CS 1102:" bullet) may not rank highly on semantic similarity
    # alone, but they are definitively relevant. This lookup is cheap
    # (metadata-only filter on ChromaDB) and feeds the reranker below.
    if course_code and "reddit" in other_sources:
        targeted = _query_collection(
            query_embedding,
            {"$and": [{"source": {"$eq": "reddit"}}, {"course_code": {"$eq": course_code}}]},
            TOP_K,
        )
        # Merge without duplicates (match on text content)
        existing_texts = {c["text"] for c in all_chunks}
        for c in targeted:
            if c["text"] not in existing_texts:
                all_chunks.append(c)
                existing_texts.add(c["text"])

    if "uopeople_course_list" in sources:
        course_list_filter = (
            {"$and": [{"source": {"$eq": "uopeople_course_list"}}, {"course_code": {"$eq": course_code}}]}
            if course_code
            else {"source": {"$eq": "uopeople_course_list"}}
        )
        all_chunks.extend(_query_collection(query_embedding, course_list_filter, TOP_K))

    if not all_chunks:
        all_chunks = _query_collection(query_embedding, None, TOP_K)

    all_chunks.sort(key=lambda c: c["distance"])

    # --- Post-retrieval reranking: surface course-specific chunks ---
    # Promote chunks that explicitly mention the queried course code to the
    # front BEFORE slicing to TOP_K — otherwise a targeted chunk added via the
    # metadata lookup above could be sorted to position 6+ by distance and then
    # discarded before the reranker ever sees it.
    if course_code:
        all_chunks = _rerank_by_course_code(all_chunks, course_code)

    return all_chunks[:TOP_K]
