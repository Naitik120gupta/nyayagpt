"""
Unit tests for backend.app.services.retrieval
"""
import pytest

import app.services.retrieval as retrieval_module
from app.services.retrieval import (
    _BM25Index,
    MultilingualLegalRetriever,
    _combine_modalities,
    _expand_query_terms,
    _normalize_query,
    _stem,
    _tokenize_text,
    is_english,
)


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


# ─── hybrid retrieval ────────────────────────────────────────────────────────


class TestHybridRetrieval:
    class _FakeEmbeddingService:
        def embed_query(self, query):
            return [0.1, 0.2, 0.3]

    class _FakeCollection:
        def __init__(self, records):
            self.records = records

        def query(self, query_embeddings, n_results, include):
            return {
                "ids": [["BNS_74_0", "BNS_308_0"]],
                "documents": [[
                    "BNS Section 74: assault modesty and harassment",
                    "BNS Section 308: extortion and intimidation",
                ]],
                "metadatas": [[
                    {"section_number": "74", "section_title": "Assault modesty"},
                    {"section_number": "308", "section_title": "Extortion"},
                ]],
                "distances": [[0.20, 0.90]],
            }

    def test_bm25_can_surface_top_hit_ahead_of_weak_vector_match(self):
        retriever = MultilingualLegalRetriever.__new__(MultilingualLegalRetriever)
        retriever.embedding_service = self._FakeEmbeddingService()
        retriever.collection = self._FakeCollection([])
        retriever._search_records = [
            {
                "id": "BNS_74_0",
                "document": "BNS Section 74: assault modesty and harassment",
                "metadata": {"section_number": "74", "section_title": "Assault modesty"},
            },
            {
                "id": "BNS_303_0",
                "document": "BNS Section 303: theft of movable property",
                "metadata": {"section_number": "303", "section_title": "Theft"},
            },
            {
                "id": "BNS_308_0",
                "document": "BNS Section 308: extortion and intimidation",
                "metadata": {"section_number": "308", "section_title": "Extortion"},
            },
        ]
        retriever._bm25_index = _BM25Index(retriever._search_records)

        payload = retriever.retrieve("theft of phone", k=2)
        results = payload["results"]

        assert len(results) == 2
        assert results[0]["metadata"]["section_number"] == "303"
        assert results[1]["metadata"]["section_number"] == "74"


# ─── stemming & query expansion ──────────────────────────────────────────────


class TestStemming:
    @pytest.mark.parametrize(
        "variants",
        [
            ("molest", "molested", "molestation"),
            ("threaten", "threatened", "threatens"),
            ("house", "houses"),
            ("kidnap", "kidnapped"),
            ("murder", "murdered"),
            ("punish", "punished", "punishment"),
        ],
    )
    def test_word_forms_share_a_stem(self, variants):
        assert len({_stem(word) for word in variants}) == 1

    def test_short_words_and_numbers_untouched(self):
        assert _stem("hit") == "hit"
        assert _stem("2023") == "2023"

    def test_trespass_not_mangled(self):
        assert _stem("trespass") == "trespass"

    def test_tokenize_applies_stemming(self):
        assert _tokenize_text("He molested her") == ["molest"]


class TestQueryExpansion:
    def test_colloquial_word_adds_legal_term(self):
        terms = _expand_query_terms("my phone was stolen")
        assert terms[_stem("theft")] > 0

    def test_typed_terms_outweigh_synonyms(self):
        terms = _expand_query_terms("he robbed me")
        assert terms[_stem("robbed")] == 1.0
        assert 0 < terms["robbery"] < 1.0

    def test_unknown_words_pass_through(self):
        terms = _expand_query_terms("xyzzy")
        assert dict(terms) == {"xyzzy": 1.0}

    def test_bm25_matches_statute_vocabulary_via_synonym(self):
        records = [
            {"id": "a", "document": "BNS Section 303: Theft. dishonestly taking movable property", "metadata": {}},
            {"id": "b", "document": "BNS Section 356: Defamation. imputation harming reputation", "metadata": {}},
        ]
        scores = _BM25Index(records).score("someone stole my wallet")
        assert scores[0] > scores[1]


# ─── fusion & section dedup ──────────────────────────────────────────────────


class TestFusion:
    def test_weighted_sum_uses_configured_vector_weight(self, monkeypatch):
        monkeypatch.setattr(retrieval_module.settings, "HYBRID_VECTOR_WEIGHT", 0.25)
        assert _combine_modalities(1.0, 0.0) == pytest.approx(0.25)
        assert _combine_modalities(0.0, 1.0) == pytest.approx(0.75)

    def test_scores_are_clamped(self):
        assert 0.0 <= _combine_modalities(5.0, -2.0) <= 1.0


class TestSectionDedup:
    class _FakeEmbeddingService:
        def embed_query(self, query):
            return [0.1, 0.2, 0.3]

    class _FakeCollection:
        def query(self, query_embeddings, n_results, include):
            return {
                "ids": [["BNS_303_0", "BNS_303_1", "BNS_303_2", "BNS_318_0"]],
                "documents": [["theft part one", "theft part two", "theft part three", "cheating"]],
                "metadatas": [[
                    {"act_name": "BNS", "section_number": "303", "chunk_index": 0},
                    {"act_name": "BNS", "section_number": "303", "chunk_index": 1},
                    {"act_name": "BNS", "section_number": "303", "chunk_index": 2},
                    {"act_name": "BNS", "section_number": "318", "chunk_index": 0},
                ]],
                "distances": [[0.10, 0.12, 0.14, 0.30]],
            }

    def test_top_k_contains_distinct_sections(self, monkeypatch):
        monkeypatch.setattr(retrieval_module.settings, "MIN_RELEVANCE_SCORE", 0.0)
        retriever = MultilingualLegalRetriever.__new__(MultilingualLegalRetriever)
        retriever.embedding_service = self._FakeEmbeddingService()
        retriever.collection = self._FakeCollection()
        retriever._search_records = []
        retriever._bm25_index = _BM25Index([])

        results = retriever.retrieve("phone taken", k=5)["results"]

        sections = [item["metadata"]["section_number"] for item in results]
        assert sections == ["303", "318"]
        assert results[0]["id"] == "BNS_303_0"

    def test_vector_scores_rescaled_within_pool(self):
        retriever = MultilingualLegalRetriever.__new__(MultilingualLegalRetriever)
        retriever.collection = self._FakeCollection()

        candidates = retriever._collect_vector_candidates([0.1], k=5)

        assert candidates[0]["vector_score"] == pytest.approx(1.0)
        assert candidates[-1]["vector_score"] == pytest.approx(0.0)
        assert candidates[0]["vector_similarity"] == pytest.approx(0.90)
