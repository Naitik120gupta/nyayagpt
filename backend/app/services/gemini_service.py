import hashlib
import logging
import sqlite3
import time
from functools import wraps

from google import genai

try:
    from backend.app.core.config import settings
except ModuleNotFoundError:
    from app.core.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Retry decorator (sync)
# ---------------------------------------------------------------------------
_RETRYABLE_CODES = ("429", "500", "503")


def _with_retry(max_attempts: int, base_delay: float):
    """Exponential-backoff retry for transient Gemini API errors (429 / 5xx)."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as exc:
                    exc_str = str(exc)
                    retryable = any(code in exc_str for code in _RETRYABLE_CODES)
                    if retryable and attempt < max_attempts - 1:
                        wait = base_delay * (2 ** attempt)  # 2 s, 4 s, 8 s …
                        logger.warning(
                            "Gemini transient error (attempt %d/%d): %s — retrying in %.1fs",
                            attempt + 1, max_attempts, exc, wait,
                        )
                        time.sleep(wait)
                        continue
                    raise
            raise RuntimeError("Gemini API failed after max retries")
        return wrapper
    return decorator


# ---------------------------------------------------------------------------
# SQLite response cache
# ---------------------------------------------------------------------------

class _ResponseCache:
    def __init__(self, db_path: str, ttl_seconds: int) -> None:
        self._ttl = ttl_seconds
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS gemini_responses (
                prompt_hash TEXT PRIMARY KEY,
                response     TEXT NOT NULL,
                created_at   INTEGER NOT NULL
            )
            """
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_created ON gemini_responses(created_at)"
        )
        self._conn.commit()

    @staticmethod
    def _hash(prompt: str) -> str:
        return hashlib.sha256(prompt.encode()).hexdigest()

    def get(self, prompt: str) -> str | None:
        row = self._conn.execute(
            "SELECT response, created_at FROM gemini_responses WHERE prompt_hash = ?",
            (self._hash(prompt),),
        ).fetchone()
        if row is None:
            return None
        response, created_at = row
        if self._ttl > 0 and (time.time() - created_at) > self._ttl:
            # Expired — delete and return miss
            self._conn.execute(
                "DELETE FROM gemini_responses WHERE prompt_hash = ?",
                (self._hash(prompt),),
            )
            self._conn.commit()
            return None
        return response

    def set(self, prompt: str, response: str) -> None:
        self._conn.execute(
            """
            INSERT OR REPLACE INTO gemini_responses (prompt_hash, response, created_at)
            VALUES (?, ?, ?)
            """,
            (self._hash(prompt), response, int(time.time())),
        )
        self._conn.commit()


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class GeminiService:
    def __init__(self):
        if not settings.GEMINI_API_KEY:
            logger.error("GEMINI_API_KEY not found in configuration.")
            self.client = None
        else:
            self.client = genai.Client(api_key=settings.GEMINI_API_KEY)

        self.generation_model = settings.GENERATION_MODEL
        self.fallback_model = settings.FALLBACK_GENERATION_MODEL
        self._cache = _ResponseCache(
            db_path=settings.GEMINI_CACHE_PATH,
            ttl_seconds=settings.GEMINI_CACHE_TTL_SECONDS,
        )
        self._generate_with_retry = _with_retry(
            max_attempts=settings.GEMINI_MAX_RETRIES,
            base_delay=settings.GEMINI_RETRY_BASE_DELAY,
        )(self._call_api)

    def _call_api(self, prompt: str, model: str | None = None) -> str:
        response = self.client.models.generate_content(
            model=model or self.generation_model,
            contents=prompt,
        )
        return response.text

    def generate_content(self, prompt: str) -> str:
        if not self.client:
            raise ValueError("Gemini API Key is missing")

        cached = self._cache.get(prompt)
        if cached is not None:
            logger.debug("Gemini cache hit (prompt hash %s…)", hashlib.sha256(prompt.encode()).hexdigest()[:8])
            return cached

        try:
            result = self._generate_with_retry(prompt)
        except Exception as exc:
            if "503" not in str(exc) and "UNAVAILABLE" not in str(exc):
                raise
            logger.warning(
                "Primary model %s unavailable (503). Falling back to %s.",
                self.generation_model,
                self.fallback_model,
            )
            result = self._call_api(prompt, model=self.fallback_model)

        self._cache.set(prompt, result)
        return result
