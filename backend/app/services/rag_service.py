try:
    from backend.app.services.retrieval import MultilingualLegalRetriever
except ModuleNotFoundError as error:
    if not (error.name or "").startswith("backend"):
        raise
    from app.services.retrieval import MultilingualLegalRetriever
import logging

logger = logging.getLogger(__name__)

class RAGService:
    def __init__(self):
        self.retriever = None
        try:
            self.retriever = MultilingualLegalRetriever()
            logger.info("Multilingual retriever initialized successfully.")
        except Exception as e:
            logger.error(f"Error initializing multilingual retriever: {e}")

    def query_similar_documents(self, query_text: str, n_results=3):
        if self.retriever is None:
            logger.error("Vector database is not available.")
            return []

        try:
            payload = self.retriever.retrieve(query_text, k=n_results)
            return [item["document"] for item in payload.get("results", [])]
        except Exception as e:
            logger.error(f"Error querying vector database: {e}")
            return []
