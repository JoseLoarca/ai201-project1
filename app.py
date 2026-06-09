"""
app.py — Application entry point.

Orchestrates all pipeline stages in order:
    1. Ingestion & chunking   (ingest.py)
    2. Embedding & storage    (embedder.py)
    3. Retrieval              (retriever.py)     — Milestone 4
    4. Generation & interface (interface.py)     — Milestone 5

Usage:
    python app.py
"""

from logger import get_session_logger

logger = get_session_logger()


def main() -> None:
    logger.info("=== The Unofficial Guide RAG — starting up ===")

    # ------------------------------------------------------------------
    # Stage 1 & 2: Ingestion → Embedding
    # Ingestion and chunking are skipped entirely when the collection is
    # already populated and FORCE_REBUILD is not set — no point chunking
    # data that won't be stored anywhere.
    # ------------------------------------------------------------------
    logger.info("=== [Stage 1/2] Ingestion & embedding ===")
    from embedder import FORCE_REBUILD, collection_is_populated, embed_and_store
    from ingest import run_ingestion

    if collection_is_populated() and not FORCE_REBUILD:
        logger.info(
            "The ChromaDB collection is already populated and FORCE_REBUILD=false. "
            "Skipping ingestion and embedding."
        )
        logger.info(
            "To rebuild from scratch, you can done of the following:\n"
            "Set FORCE_REBUILD=true in your .env file or\n"
            "Run: FORCE_REBUILD=true python app.py or\n"
            "Manually delete the collection using rm -rf chroma_db/ (Mac/Linux)."
        )
    else:
        chunks = run_ingestion()
        embed_and_store(chunks)

    # ------------------------------------------------------------------
    # Stage 3: Retrieval
    # ------------------------------------------------------------------
    logger.info("=== [Stage 3] Retrieval ===")
    from retriever import retrieve

    test_queries = [
        "Is CS2204 a difficult course?",
        "What is CS4407 about?",
        "Has anyone ever encountered any professors that give good feedback?",
        "tell me about professors who taught CS2204",
        "how to unlock the barbarian king in clash of clans"
    ]

    for query in test_queries:
        logger.info(f"{'─' * 20}")
        logger.info(f"Query: {query}")
        logger.info(f"{'─' * 20}")

        chunks = retrieve(query)

        if not chunks:
            logger.info("No chunks retrieved.")
            continue

        for i, chunk in enumerate(chunks, 1):
            logger.info(
                f"[{i}] source={chunk['metadata'].get('source')} | "
                f"file={chunk['metadata'].get('source_file')} | "
                f"course={chunk['metadata'].get('course_code') or 'N/A'} | "
                f"professor={chunk['metadata'].get('professor_name') or 'N/A'} | "
                f"distance={chunk['distance']:.4f}"
            )
            logger.info(f"Text: {chunk['text']}")

    # ------------------------------------------------------------------
    # Stage 4: Generation & interface  (Milestone 5)
    # ------------------------------------------------------------------
    logger.info("=== [Stage 4] Generation & interface — not yet implemented ===")
    # from interface import launch
    # launch()

    logger.info("=== Startup complete ===")


if __name__ == "__main__":
    main()
