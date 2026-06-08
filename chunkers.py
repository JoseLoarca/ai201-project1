"""
chunkers.py — Document-specific chunking strategies.

Each function takes preprocessed text (or pre-split reviews) and returns
a list of dicts: {"text": str, "metadata": dict}

Chunking strategies:
- RateMyProfessor: semantic (1 review = 1 chunk, already split by preprocessor)
- Reddit posts: recursive (256 tokens, 26 overlap)
- UoPeople course list: structure-based (1 course = 1 chunk)
- UoPeople degree catalog: recursive (256 tokens, 26 overlap)
"""

import re

from logger import get_session_logger

logger = get_session_logger()


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_APPROX_CHARS_PER_TOKEN = 4  # rough heuristic: 1 token ≈ 4 characters

CHUNK_SIZE_TOKENS = 256
CHUNK_OVERLAP_TOKENS = 26
CHUNK_SIZE_CHARS = CHUNK_SIZE_TOKENS * _APPROX_CHARS_PER_TOKEN
CHUNK_OVERLAP_CHARS = CHUNK_OVERLAP_TOKENS * _APPROX_CHARS_PER_TOKEN

# Ordered separators for recursive splitting: prefer natural boundaries first
_RECURSIVE_SEPARATORS = ["\n\n", "\n", ". ", " ", ""]


def _recursive_split(text: str, separators: list[str], chunk_size: int, overlap: int) -> list[str]:
    """
    Recursively split text into chunks no larger than chunk_size characters,
    with overlap between consecutive chunks.
    """
    logger.debug(f"Performing recursive split")
    separator = separators[0] if separators else ""
    remaining_seps = separators[1:]

    splits = text.split(separator) if separator else list(text)

    chunks: list[str] = []
    current = ""

    for split in splits:
        candidate = (current + separator + split).lstrip(separator) if current else split

        if len(candidate) <= chunk_size:
            current = candidate
        else:
            # Current buffer is full — flush it
            if current:
                chunks.append(current)
                # Carry overlap forward
                current = current[-overlap:].lstrip() if overlap else ""

            # If the single split itself exceeds the limit, recurse deeper
            if len(split) > chunk_size and remaining_seps:
                sub_chunks = _recursive_split(split, remaining_seps, chunk_size, overlap)
                chunks.extend(sub_chunks[:-1])
                current = sub_chunks[-1] if sub_chunks else ""
            else:
                current = split

    if current.strip():
        chunks.append(current)

    return [c.strip() for c in chunks if c.strip()]


# ---------------------------------------------------------------------------
# RateMyProfessor — semantic chunking (1 review = 1 chunk)
# ---------------------------------------------------------------------------

def chunk_rmp_reviews(
    enriched_reviews: list[str],
    header_metadata: dict,
    source_file: str,
) -> list[dict]:
    """
    Each enriched review (already metadata-injected by preprocessor) becomes one chunk.

    Args:
        enriched_reviews: output of preprocessor.preprocess_rmp_file()
        header_metadata: professor-level metadata from preprocessor.extract_rmp_header()
        source_file: filename (e.g. 'alejandro.txt') for traceability

    Returns:
        List of {"text": str, "metadata": dict}
    """
    logger.debug("Chunking RMP reviews")

    chunks = []
    professor_name = header_metadata.get("professor_name", "")

    for i, review_text in enumerate(enriched_reviews):
        # Extract course code from the review block for metadata filtering
        course_match = re.search(r"Course:\s*(CS\d{4})", review_text, re.IGNORECASE)
        course_code = course_match.group(1).upper() if course_match else ""

        # Extract tags
        tags_match = re.search(r"Tags:\s*(.+)", review_text)
        tags = [t.strip() for t in tags_match.group(1).split(",")] if tags_match else []

        logger.debug(f"Review to be chunked: {review_text}")

        chunks.append({
            "text": review_text,
            "metadata": {
                "source": "ratemyprofessor",
                "source_file": source_file,
                "professor_name": professor_name,
                "overall_quality": header_metadata.get("overall_quality"),
                "difficulty": header_metadata.get("difficulty"),
                "would_take_again_pct": header_metadata.get("would_take_again_pct"),
                "course_code": course_code,
                "tags": tags,
                "chunk_index": i,
            },
        })

    return chunks


# ---------------------------------------------------------------------------
# Reddit — recursive chunking (256t / 26 overlap)
# ---------------------------------------------------------------------------

def chunk_reddit_post(
    thread_blocks: list[str],
    source_file: str,
) -> list[dict]:
    """
    Recursively chunk a Reddit thread that has been pre-split into blocks.

    Each block represents one top-level comment thread (or the post body),
    and is chunked independently so the splitter never merges two unrelated
    threads into the same chunk.

    Args:
        thread_blocks: output of preprocessor.preprocess_reddit_file() —
                       a list of self-contained text blocks, each prefixed
                       with the post title.
        source_file: filename (e.g. 'cs_classes_you_found_them_difficult.txt')

    Returns:
        List of {"text": str, "metadata": dict}
    """
    chunks = []
    chunk_index = 0

    for block in thread_blocks:
        raw_chunks = _recursive_split(
            block,
            _RECURSIVE_SEPARATORS,
            CHUNK_SIZE_CHARS,
            CHUNK_OVERLAP_CHARS,
        )

        for chunk_text in raw_chunks:
            chunk_codes = list(
                {m.group().upper() for m in re.finditer(r"CS\d{4}", chunk_text, re.IGNORECASE)}
            )
            chunks.append({
                "text": chunk_text,
                "metadata": {
                    "source": "reddit",
                    "source_file": source_file,
                    "professor_name": "",
                    "course_code": chunk_codes[0] if len(chunk_codes) == 1 else "",
                    "tags": chunk_codes,
                    "chunk_index": chunk_index,
                },
            })
            chunk_index += 1

    return chunks


# ---------------------------------------------------------------------------
# UoPeople course list — structure-based chunking (1 course = 1 chunk)
# ---------------------------------------------------------------------------

def chunk_course_list(
    normalized_text: str,
    source_file: str,
) -> list[dict]:
    """
    Split the UoPeople course list so each course is its own chunk.
    Courses are separated by blank lines. The first two lines are a SOURCE tag and title.

    Args:
        normalized_text: output of preprocessor.preprocess_uop_course_list_file()
        source_file: filename (e.g. 'courses_in_computer_science.txt')

    Returns:
        List of {"text": str, "metadata": dict}
    """
    lines = normalized_text.splitlines()

    start_idx = 0
    state = "FIND_SOURCE"

    for idx, line in enumerate(lines):
        cleaned_line = line.strip()

        if state == "FIND_SOURCE" and cleaned_line.startswith("SOURCE:"):
            state = "FIND_DOC_TITLE"
            continue

        elif state == "FIND_DOC_TITLE" and cleaned_line:
            # This skips the document title
            state = "FIND_COURSE_START"
            continue

        elif state == "FIND_COURSE_START" and cleaned_line:
            # We found the first course!
            start_idx = idx
            break

    body = "\n".join(lines[start_idx:])

    # Split on blank lines to get individual course blocks
    raw_blocks = re.split(r"\n{2,}", body)

    chunks = []
    for i, block in enumerate(raw_blocks):
        block = block.strip()
        if not block:
            continue

        code_match = re.search(r"Course Code:\s*(CS\d{4})", block, re.IGNORECASE)
        course_code = code_match.group(1).upper() if code_match else ""

        prereq_match = re.search(r"Prerequisites:\s*(.+)", block)
        prerequisites = prereq_match.group(1).strip() if prereq_match else "None"

        credits_match = re.search(r"Credits:\s*(\d+)", block)
        credits = int(credits_match.group(1)) if credits_match else None

        # First line of the block is the course name
        course_name = block.splitlines()[0].strip()

        logger.debug(f"Course chunk: {block}")

        chunks.append({
            "text": block,
            "metadata": {
                "source": "uopeople_course_list",
                "source_file": source_file,
                "professor_name": "",
                "course_code": course_code,
                "course_name": course_name,
                "prerequisites": prerequisites,
                "credits": credits,
                "tags": [],
                "chunk_index": i,
            },
        })

    return chunks


# ---------------------------------------------------------------------------
# UoPeople degree catalog — recursive chunking (256t / 26 overlap)
# ---------------------------------------------------------------------------

def chunk_degree_catalog(
    normalized_text: str,
    source_file: str,
) -> list[dict]:
    """
    Recursively chunk the UoPeople degree catalog document.
    Attempts to preserve section-level boundaries (learning pathways, prerequisites, etc.).

    Args:
        normalized_text: output of preprocessor.preprocess_uop_catalog_file()
        source_file: filename (e.g. 'bscs_uopeople_catalog.txt')

    Returns:
        List of {"text": str, "metadata": dict}
    """
    raw_chunks = _recursive_split(
        normalized_text,
        _RECURSIVE_SEPARATORS,
        CHUNK_SIZE_CHARS,
        CHUNK_OVERLAP_CHARS,
    )

    chunks = []
    for i, chunk_text in enumerate(raw_chunks):
        chunk_codes = list(
            {m.group().upper() for m in re.finditer(r"CS\d{4}", chunk_text, re.IGNORECASE)}
        )
        chunks.append({
            "text": chunk_text,
            "metadata": {
                "source": "uopeople_catalog",
                "source_file": source_file,
                "professor_name": "",
                "course_code": chunk_codes[0] if len(chunk_codes) == 1 else "",
                "tags": chunk_codes,
                "chunk_index": i,
            },
        })

    return chunks
