"""
ingest.py — Document ingestion entry point.

Orchestrates loading, preprocessing, and chunking for all document categories.
Run this script directly to process all documents and print a summary.

Usage:
    python ingest.py
"""

from pathlib import Path

from chunkers import (
    chunk_rmp_reviews,
    chunk_reddit_post,
    chunk_course_list,
    chunk_degree_catalog,
)
from logger import get_session_logger
from preprocessor import (
    preprocess_rmp_file,
    preprocess_reddit_file,
    preprocess_uop_catalog_file,
    preprocess_uop_course_list_file,
)

DOCUMENTS_DIR = Path(__file__).parent / "documents"

RMP_DIR = DOCUMENTS_DIR / "ratemyprofessor"
REDDIT_DIR = DOCUMENTS_DIR / "reddit"
UOP_DIR = DOCUMENTS_DIR / "uop"

COURSE_LIST_FILE = "courses_in_computer_science.txt"
CATALOG_FILE = "bscs_uopeople_catalog.txt"

logger = get_session_logger()

def _read(path: Path) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


# ---------------------------------------------------------------------------
# Per-category ingestion functions
# ---------------------------------------------------------------------------

def ingest_rmp() -> list[dict]:
    """Load and chunk all RateMyProfessor review files."""
    all_chunks = []

    for txt_file in sorted(RMP_DIR.glob("*.txt")):
        raw = _read(txt_file)
        header, enriched_reviews = preprocess_rmp_file(raw)

        if not enriched_reviews:
            logger.warning(f"  [WARN] No reviews found in {txt_file.name}")
            continue

        chunks = chunk_rmp_reviews(enriched_reviews, header, txt_file.name)
        logger.info(f"  [RMP] {txt_file.name}: {len(chunks)} review chunks")
        all_chunks.extend(chunks)

    return all_chunks


def ingest_reddit() -> list[dict]:
    """Load, flatten, and chunk all Reddit thread files."""
    all_chunks = []

    for txt_file in sorted(REDDIT_DIR.glob("*.txt")):
        raw = _read(txt_file)
        thread_blocks = preprocess_reddit_file(raw)

        logger.debug(f"  [Reddit] '{txt_file.name}': {len(thread_blocks)} thread blocks")
        for i, block in enumerate(thread_blocks):
            logger.debug(f"    block {i}: {block[:120].replace(chr(10), ' ')}...")

        chunks = chunk_reddit_post(thread_blocks, txt_file.name)
        logger.info(f"  [Reddit] {txt_file.name}: {len(chunks)} chunks")
        all_chunks.extend(chunks)

    return all_chunks


def ingest_uop() -> list[dict]:
    """Load and chunk UoPeople course list and degree catalog."""
    all_chunks = []

    course_list_path = UOP_DIR / COURSE_LIST_FILE
    if course_list_path.exists():
        raw = _read(course_list_path)
        normalized = preprocess_uop_course_list_file(raw)
        chunks = chunk_course_list(normalized, COURSE_LIST_FILE)
        logger.info(f"  [UoP Course List] {COURSE_LIST_FILE}: {len(chunks)} course chunks")
        all_chunks.extend(chunks)
    else:
        logger.warning(f"  [WARN] {COURSE_LIST_FILE} not found at {course_list_path}")

    catalog_path = UOP_DIR / CATALOG_FILE
    if catalog_path.exists():
        raw = _read(catalog_path)
        normalized = preprocess_uop_catalog_file(raw)
        chunks = chunk_degree_catalog(normalized, CATALOG_FILE)
        logger.info(f"  [UoP Catalog] {CATALOG_FILE}: {len(chunks)} chunks")
        all_chunks.extend(chunks)
    else:
        logger.warning(f"  [WARN] {CATALOG_FILE} not found at {catalog_path}")

    return all_chunks


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_ingestion() -> list[dict]:
    """
    Run the full ingestion and chunking pipeline for all document categories.
    Returns the combined list of all chunks across all sources.
    """
    logger.info("=== Starting ingestion ===")

    logger.info("[1/3] RateMyProfessor reviews")
    rmp_chunks = ingest_rmp()

    logger.info("[2/3] Reddit posts")
    reddit_chunks = ingest_reddit()

    logger.info("[3/3] UoPeople documents")
    uop_chunks = ingest_uop()

    all_chunks = rmp_chunks + reddit_chunks + uop_chunks

    logger.info(f"=== Ingestion complete ===")
    logger.info(f"Total chunks: {len(all_chunks)}")
    logger.info(f"  RateMyProfessor: {len(rmp_chunks)}")
    logger.info(f"  Reddit:          {len(reddit_chunks)}")
    logger.info(f"  UoPeople:        {len(uop_chunks)}")

    return all_chunks

