from google import genai
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

        self.generation_model = settings.GENERATION_MODEL

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
