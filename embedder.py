"""
embedder.py — Embedding and vector storage.

Responsibilities:
- Load the all-MiniLM-L6-v2 embedding model via sentence-transformers
- Manage a persistent ChromaDB collection
- Embed chunk texts and store them with metadata
- Guard against redundant re-embedding via env var control

Environment variables (all optional):
    CHROMA_PATH         Path where ChromaDB persists its data.
                        Default: ./chroma_db
    CHROMA_COLLECTION   Name of the ChromaDB collection.
                        Default: theunofficialguide
    FORCE_REBUILD       Set to "true" to wipe and rebuild the collection
                        even if it is already populated.
                        Default: false
"""

import os
from typing import Optional

import chromadb
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer

from logger import get_session_logger

load_dotenv()

logger = get_session_logger()

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"
CHROMA_PATH = os.getenv("CHROMA_PATH", "./chroma_db")
CHROMA_COLLECTION_NAME = os.getenv("CHROMA_COLLECTION", "theunofficialguide")
FORCE_REBUILD = os.getenv("FORCE_REBUILD", "false").strip().lower() == "true"

# ---------------------------------------------------------------------------
# Module-level singletons (loaded once, reused across calls)
# ---------------------------------------------------------------------------

_embedding_model: Optional[SentenceTransformer] = None
_chroma_client: Optional[chromadb.api.client.Client] = None


def _get_embedding_model() -> SentenceTransformer:
    global _embedding_model
    if _embedding_model is None:
        logger.info(f"Loading embedding model '{EMBEDDING_MODEL_NAME}'...")
        _embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME)
        logger.info("Embedding model loaded.")
    return _embedding_model


def _get_chroma_client() -> chromadb.api.client.Client:
    global _chroma_client
    if _chroma_client is None:
        _chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)
    return _chroma_client


# ---------------------------------------------------------------------------
# Metadata sanitization
# ---------------------------------------------------------------------------

def _sanitize_metadata(metadata: dict) -> dict:
    """
    ChromaDB only accepts metadata values that are str, int, float, or bool.
    This function:
    - Converts lists to comma-separated strings (e.g. tags)
    - Replaces None with an empty string
    - Leaves all other types untouched
    """
    sanitized = {}
    for key, value in metadata.items():
        if value is None:
            sanitized[key] = ""
        elif isinstance(value, list):
            sanitized[key] = ", ".join(str(v) for v in value)
        else:
            sanitized[key] = value
    return sanitized


# ---------------------------------------------------------------------------
# Collection management
# ---------------------------------------------------------------------------

def _is_collection_populated(collection: chromadb.Collection) -> bool:
    """Return True if the collection already contains at least one document."""
    return collection.count() > 0


def collection_is_populated() -> bool:
    """
    Public helper for app.py to check whether the collection already has data
    before deciding whether to run ingestion and chunking at all.
    """
    client = _get_chroma_client()
    collection = client.get_or_create_collection(name=CHROMA_COLLECTION_NAME)
    return _is_collection_populated(collection)


def _get_collection(force_rebuild: bool) -> chromadb.Collection:
    """
    Get (or create) the ChromaDB collection, applying rebuild logic:
    - If the collection is empty → use it as-is (will be populated by embed_and_store).
    - If populated and force_rebuild=True → delete and recreate.
    - If populated and force_rebuild=False → return as-is (caller should skip embedding).
    """
    client = _get_chroma_client()
    collection = client.get_or_create_collection(
        name=CHROMA_COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )

    if _is_collection_populated(collection):
        if force_rebuild:
            logger.info(
                f"FORCE_REBUILD=true — deleting and recreating "
                f"collection '{CHROMA_COLLECTION_NAME}'."
            )
            client.delete_collection(CHROMA_COLLECTION_NAME)
            collection = client.create_collection(
                name=CHROMA_COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"},
            )
        else:
            logger.info(
                f"Collection '{CHROMA_COLLECTION_NAME}' is already populated "
                f"({collection.count()} chunks). Skipping embedding."
            )
            logger.info(
                "To force a full wipe and rebuild, set FORCE_REBUILD=true in your .env file "
                "or run: FORCE_REBUILD=true python embedder.py"
            )

    return collection


# ---------------------------------------------------------------------------
# Embedding + storage
# ---------------------------------------------------------------------------

def embed_and_store(chunks: list[dict]) -> None:
    """
    Embed all chunks and store them in ChromaDB.

    Each chunk is expected to be a dict with:
        "text"     — the chunk text to embed
        "metadata" — dict with source, source_file, professor_name,
                     course_code, tags, chunk_index, and any other fields

    If the collection is already populated and FORCE_REBUILD is not set,
    this function exits early with an informational message.

    Args:
        chunks: combined output of run_ingestion() from ingest.py
    """
    logger.info("=== Starting embedding ===")
    collection = _get_collection(force_rebuild=FORCE_REBUILD)

    if _is_collection_populated(collection):
        # Already populated and FORCE_REBUILD=false — skip embedding
        return

    if not chunks:
        logger.warning("No chunks provided to embed_and_store(). Nothing to do.")
        return

    model = _get_embedding_model()

    logger.info(f"Embedding {len(chunks)} chunks...")

    texts = [chunk["text"] for chunk in chunks]
    embeddings = model.encode(texts, show_progress_bar=True, convert_to_list=True)

    ids = [
        f"{chunk['metadata']['source_file']}__chunk_{chunk['metadata']['chunk_index']}"
        for chunk in chunks
    ]
    metadatas = [_sanitize_metadata(chunk["metadata"]) for chunk in chunks]

    # ChromaDB recommends batching large upserts
    batch_size = 500
    for start in range(0, len(chunks), batch_size):
        end = start + batch_size
        collection.add(
            ids=ids[start:end],
            embeddings=embeddings[start:end],
            documents=texts[start:end],
            metadatas=metadatas[start:end],
        )
        logger.info(f"  Stored batch {start // batch_size + 1}: chunks {start}–{min(end, len(chunks)) - 1}")

    logger.info(
        f"Done. {len(chunks)} chunks embedded and stored in "
        f"collection '{CHROMA_COLLECTION_NAME}' at '{CHROMA_PATH}'."
    )
