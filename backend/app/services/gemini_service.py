import google.generativeai as genai
from backend.app.core.config import settings
import logging

logger = logging.getLogger(__name__)

class GeminiService:
    def __init__(self):
        if not settings.GEMINI_API_KEY:
            logger.error("GEMINI_API_KEY not found in configuration.")
        else:
            genai.configure(api_key=settings.GEMINI_API_KEY)

        self.embedding_model = settings.EMBEDDING_MODEL
        self.generation_model = settings.GENERATION_MODEL

    def get_embedding(self, text: str):
        if not settings.GEMINI_API_KEY:
             raise ValueError("Gemini API Key is missing")
        try:
            result = genai.embed_content(
                model=self.embedding_model,
                content=text,
                task_type="retrieval_query"
            )
            return result['embedding']
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            raise

    def generate_content(self, prompt: str):
        if not settings.GEMINI_API_KEY:
             raise ValueError("Gemini API Key is missing")
        try:
            model = genai.GenerativeModel(self.generation_model)
            response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            logger.error(f"Error generating content: {e}")
            raise
