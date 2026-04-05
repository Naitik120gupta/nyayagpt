import os
import sys
import logging

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

try:
    from backend.app.core.config import settings
    from backend.app.services.ingestion import ingest_legal_corpus
except ModuleNotFoundError as error:
    if not (error.name or "").startswith("backend"):
        raise
    from app.core.config import settings
    from app.services.ingestion import ingest_legal_corpus


logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def main():
    logger.info("--- Starting Data Ingestion (InLegalBERT + Chroma) ---")
    try:
        indexed_count = ingest_legal_corpus(settings.BNS_DATA_PATH)
        logger.info("Successfully indexed %s chunks into vector store.", indexed_count)
        logger.info("--- Data Ingestion Complete ---")
    except Exception as error:
        logger.error("Ingestion failed: %s", error)
        raise

if __name__ == "__main__":
    main()
