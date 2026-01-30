import chromadb
import os
from backend.app.core.config import settings
import logging

logger = logging.getLogger(__name__)

class RAGService:
    def __init__(self):
        self.collection = None
        try:
            if not os.path.exists(settings.VECTOR_STORE_DIR):
                logger.warning(f"Vector store directory not found at {settings.VECTOR_STORE_DIR}. Run ingest script first.")

            self.client = chromadb.PersistentClient(path=settings.VECTOR_STORE_DIR)
            try:
                self.collection = self.client.get_collection(name=settings.COLLECTION_NAME)
                logger.info(f"Successfully connected to collection: {settings.COLLECTION_NAME}")
            except Exception as e:
                logger.warning(f"Collection {settings.COLLECTION_NAME} not found. Run ingest script first.")

        except Exception as e:
            logger.error(f"Error connecting to vector database: {e}")

    def query_similar_documents(self, query_embedding, n_results=3):
        if self.collection is None:
            logger.error("Vector database is not available.")
            return []

        try:
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results
            )
            return results['documents'][0] if results['documents'] else []
        except Exception as e:
            logger.error(f"Error querying vector database: {e}")
            return []
