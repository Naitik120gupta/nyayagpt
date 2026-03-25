from google import genai
from google.genai import types
try:
    from backend.app.core.config import settings
except ModuleNotFoundError:
    from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

class GeminiService:
    def __init__(self):
        if not settings.GEMINI_API_KEY:
            logger.error("GEMINI_API_KEY not found in configuration.")
            self.client = None
        else:
            self.client = genai.Client(api_key=settings.GEMINI_API_KEY)

        self.embedding_model = settings.EMBEDDING_MODEL
        self.generation_model = settings.GENERATION_MODEL

    def get_embedding(self, text: str):
        if not self.client:
            raise ValueError("Gemini API Key is missing")
        try:
            result = self.client.models.embed_content(
                model=self.embedding_model,
                contents=text,
                config=types.EmbedContentConfig(task_type="RETRIEVAL_QUERY")
            )
            return result.embeddings[0].values
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            raise

    def generate_content(self, prompt: str):
        if not self.client:
            raise ValueError("Gemini API Key is missing")
        try:
            response = self.client.models.generate_content(
                model=self.generation_model,
                contents=prompt
            )
            return response.text
        except Exception as e:
            logger.error(f"Error generating content: {e}")
            raise
