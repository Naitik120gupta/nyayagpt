"""
Unit tests for backend.app.services.gemini_service

All external calls (google.genai) are mocked.
"""
import time
from unittest.mock import MagicMock, patch, call

import pytest

from app.services.gemini_service import GeminiService, _ResponseCache, _with_retry


# ─── _ResponseCache ───────────────────────────────────────────────────────────

class TestResponseCache:
    def test_miss_returns_none(self, tmp_db):
        cache = _ResponseCache(tmp_db, ttl_seconds=3600)
        assert cache.get("hello") is None

    def test_set_then_get_returns_value(self, tmp_db):
        cache = _ResponseCache(tmp_db, ttl_seconds=3600)
        cache.set("prompt", "response text")
        assert cache.get("prompt") == "response text"

    def test_different_prompts_independent(self, tmp_db):
        cache = _ResponseCache(tmp_db, ttl_seconds=3600)
        cache.set("p1", "r1")
        cache.set("p2", "r2")
        assert cache.get("p1") == "r1"
        assert cache.get("p2") == "r2"

    def test_overwrite_replaces_value(self, tmp_db):
        cache = _ResponseCache(tmp_db, ttl_seconds=3600)
        cache.set("p", "old")
        cache.set("p", "new")
        assert cache.get("p") == "new"

    def test_expired_entry_returns_none(self, tmp_db):
        cache = _ResponseCache(tmp_db, ttl_seconds=1)
        cache.set("p", "value")
        # Manually backdate the entry
        import sqlite3
        with sqlite3.connect(tmp_db) as conn:
            conn.execute("UPDATE gemini_responses SET created_at = created_at - 10")
        assert cache.get("p") is None

    def test_ttl_zero_never_expires(self, tmp_db):
        cache = _ResponseCache(tmp_db, ttl_seconds=0)
        cache.set("p", "value")
        import sqlite3
        with sqlite3.connect(tmp_db) as conn:
            conn.execute("UPDATE gemini_responses SET created_at = 0")
        assert cache.get("p") == "value"

    def test_expired_entry_deleted_from_db(self, tmp_db):
        import sqlite3
        cache = _ResponseCache(tmp_db, ttl_seconds=1)
        cache.set("p", "value")
        with sqlite3.connect(tmp_db) as conn:
            conn.execute("UPDATE gemini_responses SET created_at = created_at - 10")
        cache.get("p")  # triggers delete
        with sqlite3.connect(tmp_db) as conn:
            count = conn.execute("SELECT COUNT(*) FROM gemini_responses").fetchone()[0]
        assert count == 0


# ─── _with_retry ──────────────────────────────────────────────────────────────

class TestWithRetry:
    def _wrap(self, fn, max_attempts=3, base_delay=0):
        return _with_retry(max_attempts=max_attempts, base_delay=base_delay)(fn)

    def test_success_on_first_attempt(self):
        fn = MagicMock(return_value="ok")
        result = self._wrap(fn)("x")
        assert result == "ok"
        assert fn.call_count == 1

    def test_retries_on_429(self):
        fn = MagicMock(side_effect=[Exception("429 Too Many Requests"), "ok"])
        with patch("time.sleep"):
            result = self._wrap(fn)("x")
        assert result == "ok"
        assert fn.call_count == 2

    def test_retries_on_500(self):
        fn = MagicMock(side_effect=[Exception("500 Internal Server Error"), "ok"])
        with patch("time.sleep"):
            result = self._wrap(fn)("x")
        assert result == "ok"

    def test_retries_on_503(self):
        fn = MagicMock(side_effect=[Exception("503 Service Unavailable"), "ok"])
        with patch("time.sleep"):
            result = self._wrap(fn)("x")
        assert result == "ok"

    def test_no_retry_on_non_retryable_error(self):
        fn = MagicMock(side_effect=ValueError("bad input"))
        with pytest.raises(ValueError):
            self._wrap(fn)("x")
        assert fn.call_count == 1

    def test_exhausts_retries_and_raises_original(self):
        fn = MagicMock(side_effect=Exception("429 rate limit"))
        with patch("time.sleep"):
            with pytest.raises(Exception, match="429"):
                self._wrap(fn, max_attempts=3)("x")
        assert fn.call_count == 3

    def test_exponential_backoff_delays(self):
        fn = MagicMock(side_effect=[
            Exception("429"), Exception("429"), "ok"
        ])
        with patch("time.sleep") as mock_sleep:
            self._wrap(fn, max_attempts=3, base_delay=2)("x")
        delays = [c.args[0] for c in mock_sleep.call_args_list]
        assert delays == [2.0, 4.0]  # 2^0 * 2, 2^1 * 2

    def test_no_sleep_on_non_retryable(self):
        fn = MagicMock(side_effect=Exception("400 Bad Request"))
        with patch("time.sleep") as mock_sleep:
            with pytest.raises(Exception):
                self._wrap(fn)("x")
        mock_sleep.assert_not_called()


# ─── GeminiService ────────────────────────────────────────────────────────────
#
# Build service instances directly (bypass __init__) to avoid settings mutation.

def _build_service(tmp_db, max_retries=3, base_delay=0.0):
    """Construct a GeminiService without calling __init__ or touching settings."""
    svc = GeminiService.__new__(GeminiService)
    svc.generation_model = "models/gemini-2.5-flash"
    svc._cache = _ResponseCache(tmp_db, ttl_seconds=3600)
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value.text = "gemini response"
    svc.client = mock_client
    svc._generate_with_retry = _with_retry(
        max_attempts=max_retries, base_delay=base_delay
    )(svc._call_api)
    return svc


class TestGeminiService:
    def test_generate_content_calls_api_on_miss(self, tmp_db):
        svc = _build_service(tmp_db)
        result = svc.generate_content("what is theft?")
        assert result == "gemini response"
        svc.client.models.generate_content.assert_called_once()

    def test_generate_content_cache_hit_skips_api(self, tmp_db):
        svc = _build_service(tmp_db)
        svc._cache.set("what is theft?", "cached response")
        result = svc.generate_content("what is theft?")
        assert result == "cached response"
        svc.client.models.generate_content.assert_not_called()

    def test_generate_content_stores_result_in_cache(self, tmp_db):
        svc = _build_service(tmp_db)
        svc.generate_content("what is rape?")
        assert svc._cache.get("what is rape?") == "gemini response"

    def test_generate_content_raises_without_client(self, tmp_db):
        svc = _build_service(tmp_db)
        svc.client = None
        with pytest.raises(ValueError, match="missing"):
            svc.generate_content("query")

    def test_generate_content_retries_on_429(self, tmp_db):
        svc = _build_service(tmp_db)
        svc.client.models.generate_content.side_effect = [
            Exception("429 rate limit"),
            MagicMock(text="ok after retry"),
        ]
        with patch("time.sleep"):
            result = svc.generate_content("retry prompt")
        assert result == "ok after retry"
        assert svc.client.models.generate_content.call_count == 2
