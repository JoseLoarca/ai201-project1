"""
generator.py — Answer generation via Groq (llama-3.3-70b-versatile).

Responsibilities:
- Assemble retrieved chunks into a labeled context block
- Send the query + context to Llama via Groq
- Return a grounded answer that always cites source files
- Refuse to speculate when context is insufficient
"""

import os

from groq import Groq
from dotenv import load_dotenv

from logger import get_session_logger

load_dotenv()

logger = get_session_logger()

GROQ_MODEL = "llama-3.3-70b-versatile"

_groq_client: Groq | None = None


def _get_groq_client() -> Groq:
    global _groq_client
    if _groq_client is None:
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError(
                "GROQ_API_KEY is not set. Add it to your .env file."
            )
        _groq_client = Groq(api_key=api_key)
    return _groq_client


# ---------------------------------------------------------------------------
# Context assembly
# ---------------------------------------------------------------------------

def _assemble_context(chunks: list[dict]) -> str:
    """
    Format retrieved chunks into a labeled context block for the prompt.
    Each chunk is prefixed with its source file so the model can cite it.

    Example output:
        [Source: alejandro.txt]
        Professor: Alejandro Lara | Overall Quality: 3.7/5 ...

        [Source: cs_classes_you_found_them_difficult.txt]
        [Thread from post: "CS classes you found them difficult"] ...
    """
    parts = []
    for chunk in chunks:
        source_file = chunk["metadata"].get("source_file", "unknown")
        parts.append(f"[Source: {source_file}]\n{chunk['text'].strip()}")
    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """You are a helpful academic assistant for students at University of the People (UoPeople) studying Computer Science.

You will be given a question and a set of context excerpts retrieved from student reviews, Reddit posts, and official UoPeople documents.

Rules you must follow:
1. Answer ONLY using information present in the provided context. Do not use any outside knowledge.
2. Every claim you make must be traceable to a specific source. Always cite the source file(s) in your answer, for example: (ratemyprofessor: alejandro.txt) or (courses_in_computer_science.txt).
3. If the context does not contain enough information to answer the question, respond with exactly: "I don't have enough information on that."
4. Do not speculate, infer, or fill gaps with general knowledge.
5. Be concise and direct. Do not repeat yourself."""


def _build_user_message(query: str, context: str) -> str:
    return f"""Context:
{context}

Question: {query}"""


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------

def generate(query: str, chunks: list[dict]) -> str:
    """
    Generate a grounded answer for the given query using the retrieved chunks.

    Args:
        query:  The user's original question.
        chunks: Output of retriever.retrieve() — list of dicts with
                keys: text, metadata, distance.

    Returns:
        A string answer that cites its sources, or "I don't have enough
        information on that." if the context is insufficient.
    """
    if not chunks:
        logger.warning("generate() called with no chunks — returning fallback.")
        return "I don't have enough information on that."

    context = _assemble_context(chunks)
    logger.debug(f"Assembled context:\n{context}")

    client = _get_groq_client()

    logger.info(f"Sending query to {GROQ_MODEL} via Groq...")
    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": _build_user_message(query, context)},
        ],
        temperature=0.2,  # low temperature for factual, grounded answers
    )

    answer = response.choices[0].message.content.strip()
    logger.info(f"Answer generated ({len(answer)} chars).")
    return answer
