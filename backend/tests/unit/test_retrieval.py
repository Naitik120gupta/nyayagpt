"""
Unit tests for backend.app.services.retrieval
"""
import pytest

from app.services.retrieval import _normalize_query, is_english


# ─── _normalize_query ────────────────────────────────────────────────────────

class TestNormalizeQuery:
    def test_strips_leading_trailing_spaces(self):
        assert _normalize_query("  theft  ") == "theft"

    def test_collapses_internal_whitespace(self):
        assert _normalize_query("my  phone  was  stolen") == "my phone was stolen"

    def test_empty_string(self):
        assert _normalize_query("") == ""

    def test_none_becomes_empty(self):
        assert _normalize_query(None) == ""

    def test_tabs_and_newlines_collapsed(self):
        assert _normalize_query("theft\n\nof\t\tproperty") == "theft of property"


# ─── is_english ──────────────────────────────────────────────────────────────

class TestIsEnglish:
    def test_plain_english_true(self):
        assert is_english("Someone stole my phone")

    def test_hindi_devanagari_false(self):
        assert not is_english("मेरे घर में चोरी हुई")

    def test_mixed_ascii_special_true(self):
        assert is_english("I was robbed at 10:30 PM near MG Road!")

    def test_empty_string_false(self):
        assert not is_english("")

    def test_non_ascii_false(self):
        assert not is_english("Böse Tat")

    def test_punctuation_only_true(self):
        # Pure ASCII punctuation passes the ASCII check
        assert is_english("!!!")


# ─── score threshold filtering ───────────────────────────────────────────────
#
# We test the threshold logic directly by simulating what retrieve() does:
# build a results list with score = 1 - distance, then filter.

class TestScoreThreshold:
    def _make_result(self, distance):
        score = (1.0 - distance) if distance is not None else 1.0
        return {
            "id": "BNS_74_0",
            "document": "BNS Section 74",
            "metadata": {},
            "distance": distance,
            "score": score,
        }

    def _filter(self, results, threshold):
        filtered = [r for r in results if r.get("score", 1.0) >= threshold]
        if not filtered:
            raise ValueError(
                "No sufficiently relevant BNS sections found for this query. "
                "Please describe the incident in more detail."
            )
        return filtered

    def test_good_results_pass_through(self):
        results = [self._make_result(0.10), self._make_result(0.20)]
        out = self._filter(results, 0.72)
        assert len(out) == 2

    def test_poor_results_filtered_out(self):
        results = [self._make_result(0.10), self._make_result(0.50)]
        out = self._filter(results, 0.72)
        # score = 1-0.50 = 0.50 < 0.72 → dropped
        assert len(out) == 1
        assert round(out[0]["score"], 2) == 0.90

    def test_exactly_at_threshold_included(self):
        results = [self._make_result(0.28)]  # score = 0.72
        out = self._filter(results, 0.72)
        assert len(out) == 1

    def test_all_below_threshold_raises_valueerror(self):
        results = [self._make_result(0.80), self._make_result(0.90)]
        with pytest.raises(ValueError, match="more detail"):
            self._filter(results, 0.72)

    def test_none_distance_defaults_to_score_one(self):
        r = self._make_result(None)
        assert r["score"] == 1.0
        out = self._filter([r], 0.72)
        assert len(out) == 1

    def test_zero_threshold_keeps_all(self):
        results = [self._make_result(0.99), self._make_result(0.80)]
        out = self._filter(results, 0.0)
        assert len(out) == 2
