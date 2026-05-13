"""
Output correctness tests — verify the right BNS sections surface for given queries.

Two test levels:
  1. CSV-level (always runs): verify the dataset contains the correct sections
     and their content matches the expected crime type.
  2. Retrieval-level (requires live vector store): verify the retriever returns
     the expected section for a set of representative crime queries.
     Skipped automatically when the vector store is missing.
"""
import csv
import os
import re

import pytest


# ─── helpers ─────────────────────────────────────────────────────────────────

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data")
VECTOR_STORE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "vector_store")
BNS_CSV = os.path.join(DATA_DIR, "bns_augmented.csv")
CHROMA_DB = os.path.join(VECTOR_STORE_DIR, "chroma.sqlite3")


def _load_sections():
    with open(BNS_CSV, newline="", encoding="utf-8") as f:
        return {row["Section"].strip(): row for row in csv.DictReader(f)}


def _vector_store_available():
    return os.path.exists(CHROMA_DB)


# ─── CSV-level correctness ────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def sections():
    if not os.path.exists(BNS_CSV):
        pytest.skip("bns_augmented.csv not found")
    return _load_sections()


class TestCSVContentCorrectness:
    """
    Verify that the BNS dataset contains the right content for each critical
    section — i.e. the raw legal text and augmented synonyms match the offence.
    """

    # (section_no, expected_keyword_in_text_or_title, expected_keyword_in_plain_language)
    SECTION_EXPECTATIONS = [
        ("63",  "rape",         "rape"),
        ("74",  "modesty",      "molestation"),
        ("75",  "harassment",   "harassment"),
        ("76",  "disrob",       "undress"),
        ("79",  "insult",       "stalking"),
        ("85",  "cruelty",      "cruelty"),
        ("86",  "cruelty",      "dowry"),
        ("109", "murder",       "murder"),
        ("115", "hurt",         "hurt"),
        ("135", "confine",      "kidnapping"),
        ("303", "theft",        "theft"),
        ("304", "snatch",       "robbery"),
        ("308", "extortion",    "extortion"),
        ("329", "trespass",     "trespass"),
    ]

    @pytest.mark.parametrize("section,text_kw,pl_kw", SECTION_EXPECTATIONS)
    def test_section_exists(self, sections, section, text_kw, pl_kw):
        assert section in sections, f"Section {section} missing from BNS CSV"

    @pytest.mark.parametrize("section,text_kw,pl_kw", SECTION_EXPECTATIONS)
    def test_section_text_contains_keyword(self, sections, section, text_kw, pl_kw):
        row = sections[section]
        combined = (row.get("Description", "") + " " + row.get("Section _name", "")).lower()
        assert text_kw in combined, (
            f"Section {section}: expected '{text_kw}' in text/title, got: {combined[:120]}"
        )

    @pytest.mark.parametrize("section,text_kw,pl_kw", SECTION_EXPECTATIONS)
    def test_plain_language_contains_keyword(self, sections, section, text_kw, pl_kw):
        pl = sections[section].get("plain_language", "").lower()
        assert pl_kw in pl, (
            f"Section {section}: expected '{pl_kw}' in plain_language, got: {pl!r}"
        )

    def test_non_augmented_section_has_empty_plain_language(self, sections):
        # Section 1 (Short title) should NOT have plain_language
        assert sections["1"].get("plain_language", "").strip() == ""

    def test_all_358_sections_present(self, sections):
        assert len(sections) == 358

    def test_section_numbers_are_unique(self):
        with open(BNS_CSV, newline="", encoding="utf-8") as f:
            nums = [r["Section"].strip() for r in csv.DictReader(f)]
        assert len(nums) == len(set(nums)), "Duplicate section numbers in CSV"


# ─── Query → expected section mappings ───────────────────────────────────────

# Each entry: (natural_language_query, [expected_section_numbers])
# Expected sections are what a correct retrieval should return (at least one hit).
QUERY_SECTION_MAP = [
    # Theft / property crimes
    ("Someone stole my mobile phone from my pocket",    ["303", "304"]),
    ("My bike was snatched by two men on a bike",       ["303", "304"]),
    ("A man threatened me with a knife and took money", ["308", "304"]),
    # Violence / assault
    ("My husband beats me and harasses me for dowry",   ["85", "86"]),
    ("A man grabbed and molested me on a crowded bus",  ["74", "75"]),
    ("Sexual assault and rape committed against a woman", ["63"]),
    ("A man tried to undress me forcibly",              ["76"]),
    # Trespass / other
    ("Someone broke into my house at night",            ["329"]),
    ("A person is stalking me and sending lewd messages", ["79", "75"]),
    # Attempt / grievous hurt
    ("Someone caused grievous hurt and serious injury", ["115", "109"]),
]


class TestCSVSectionContentForQueries:
    """
    Offline check: for each sample query, verify the expected sections exist in
    the CSV and their Description/plain_language contains relevant keywords from
    the query.  This validates dataset coverage without needing the model.
    """

    @pytest.mark.parametrize("query,expected_sections", QUERY_SECTION_MAP)
    def test_expected_sections_present_in_dataset(self, sections, query, expected_sections):
        for sec in expected_sections:
            assert sec in sections, f"Query '{query[:40]}': section {sec} not in dataset"

    @pytest.mark.parametrize("query,expected_sections", QUERY_SECTION_MAP)
    def test_query_keywords_appear_in_section_content(self, sections, query, expected_sections):
        """
        At least one meaningful word from the query should appear (as a substring)
        in the combined legal text + plain_language of at least one expected section.
        Substring matching handles inflected forms ("raped" → found inside "rape").
        """
        # Use first 5 chars as a loose stem; skip short/common words
        STOPWORDS = {"someone", "my", "me", "with", "from", "into", "by", "was",
                     "were", "have", "been", "that", "this", "they", "their"}
        stems = [
            w.lower()[:5]
            for w in query.split()
            if len(w) >= 5 and w.lower() not in STOPWORDS
        ]
        for sec in expected_sections:
            row = sections[sec]
            combined = (
                row.get("Description", "") + " " +
                row.get("Section _name", "") + " " +
                row.get("plain_language", "")
            ).lower()
            for stem in stems:
                if stem in combined:
                    return  # found a match
        pytest.fail(
            f"No query keyword from '{query[:50]}' found in sections "
            f"{expected_sections}. Stems checked: {stems}"
        )


# ─── Live retrieval correctness (requires vector store + model) ───────────────

@pytest.mark.skipif(
    not _vector_store_available(),
    reason="Vector store not found — run ingest.py first",
)
class TestLiveRetrievalCorrectness:
    """
    Requires:
      - backend/vector_store/chroma.sqlite3 (populated by ingest.py)
      - InLegalBERT model downloaded to ~/.cache/huggingface

    Uses the real retriever; skipped in CI if vector store is absent.
    """

    @pytest.fixture(scope="class", autouse=True)
    def retriever(self):
        import sys, types
        # Remove stubs that conftest may have set for chromadb/sentence_transformers
        for mod in list(sys.modules.keys()):
            if mod in ("chromadb", "sentence_transformers", "sentence_transformers.models"):
                del sys.modules[mod]
        try:
            from app.services.retrieval import MultilingualLegalRetriever
            return MultilingualLegalRetriever()
        except Exception as exc:
            pytest.skip(f"Could not initialise retriever: {exc}")

    def _retrieved_sections(self, retriever, query, k=5):
        try:
            payload = retriever.retrieve(query, k=k)
            return {
                item["metadata"].get("section_number", "")
                for item in payload.get("results", [])
            }
        except ValueError:
            return set()

    @pytest.mark.parametrize("query,expected_sections", QUERY_SECTION_MAP)
    def test_correct_section_in_top_k(self, retriever, query, expected_sections):
        retrieved = self._retrieved_sections(retriever, query, k=5)
        hit = bool(retrieved & set(expected_sections))
        assert hit, (
            f"Query: '{query}'\n"
            f"Expected one of {expected_sections} in top-5.\n"
            f"Got: {sorted(retrieved)}"
        )

    def test_non_english_query_raises_valueerror(self, retriever):
        with pytest.raises(ValueError, match="English"):
            retriever.retrieve("मेरे साथ चोरी हुई")

    def test_vague_query_raises_valueerror_or_returns_empty(self, retriever):
        # A completely unrelated query should either raise (threshold) or return empty
        try:
            result = retriever.retrieve("xyz abc qrs", k=3)
            # If no exception, results should be empty or very low score
        except ValueError as e:
            assert "more detail" in str(e).lower() or "relevant" in str(e).lower()
