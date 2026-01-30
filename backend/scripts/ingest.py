import sys
import os

# Add the project root to sys.path to allow imports from backend.app
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

import chromadb
import re
import logging
import google.generativeai as genai
from backend.app.core.config import settings

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

def main():
    logger.info("--- Starting Data Ingestion ---")

    # Configure Gemini API
    if not settings.GEMINI_API_KEY:
        logger.error("GEMINI_API_KEY not found in configuration.")
        return
    genai.configure(api_key=settings.GEMINI_API_KEY)

    # 1. Load Data
    logger.info(f"Loading data from {settings.IPC_DATA_PATH}")
    try:
        with open(settings.IPC_DATA_PATH, 'r', encoding='utf-8') as f:
            raw_legal_text = f.read()
    except FileNotFoundError:
        logger.error(f"Data file not found at {settings.IPC_DATA_PATH}")
        return

    # 2. Parse Data
    section_pattern = re.compile(r"Section (\d+): (.+?)\n(.+?)(?=\nSection|\Z)", re.DOTALL)
    legal_sections = [{"id": f"ipc_{m.group(1).strip()}", "document": f"Section {m.group(1).strip()}: {m.group(2).strip()}. {m.group(3).strip().replace(chr(10), ' ')}"} for m in section_pattern.finditer(raw_legal_text)]

    logger.info(f"Parsed {len(legal_sections)} sections.")

    # 3. Create Embeddings with Gemini API
    logger.info(f"Generating embeddings with Gemini model: {settings.EMBEDDING_MODEL}...")
    try:
        # Batching might be needed if too many sections, but for now keeping it simple as per original
        embedding_result = genai.embed_content(
            model=settings.EMBEDDING_MODEL,
            content=[s['document'] for s in legal_sections],
            task_type="retrieval_document"
        )
        embeddings = embedding_result['embedding']
        logger.info("Embeddings generated successfully.")
    except Exception as e:
        logger.error(f"Failed to generate embeddings with Gemini API: {e}")
        return

    # 4. Initialize and Populate Vector DB
    # Create directory if it doesn't exist
    os.makedirs(settings.VECTOR_STORE_DIR, exist_ok=True)
    logger.info(f"Vector Store Path: {settings.VECTOR_STORE_DIR}")

    chroma_client = chromadb.PersistentClient(path=settings.VECTOR_STORE_DIR)

    # Check if collection exists and delete it
    try:
         # List collections returns objects, need to check names
         collections = chroma_client.list_collections()
         if any(c.name == settings.COLLECTION_NAME for c in collections):
             chroma_client.delete_collection(name=settings.COLLECTION_NAME)
    except Exception as e:
        logger.warning(f"Warning during collection deletion: {e}")

    vector_collection = chroma_client.create_collection(name=settings.COLLECTION_NAME)
    vector_collection.add(
        embeddings=embeddings,
        documents=[s['document'] for s in legal_sections],
        ids=[s['id'] for s in legal_sections]
    )

    logger.info(f"Successfully added {vector_collection.count()} documents to the vector store.")
    logger.info("--- Data Ingestion Complete ---")

if __name__ == "__main__":
    main()
