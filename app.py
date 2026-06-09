"""
app.py — Application entry point.

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
    logger.info("=== Ingestion & embedding ===")
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


    logger.info("=== Interface launch ===")
    from interface import launch
    launch()

    logger.info("=== Bye. ===")


if __name__ == "__main__":
    main()
