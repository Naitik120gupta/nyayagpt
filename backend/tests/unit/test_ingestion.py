"""
Unit tests for backend.app.services.ingestion
"""
import csv
import io
import os
import tempfile
import textwrap

import pytest

from app.services.ingestion import (
    _chunk_text,
    _sanitize_id,
    _sections_from_csv,
    _split_into_sentences,
    build_chunks,
)


# ─── _sanitize_id ────────────────────────────────────────────────────────────

class TestSanitizeId:
    def test_replaces_spaces(self):
        assert _sanitize_id("BNS 74") == "BNS_74"

    def test_replaces_dots(self):
        assert _sanitize_id("3.1") == "3_1"

    def test_alphanumeric_unchanged(self):
        assert _sanitize_id("abc123") == "abc123"

    def test_empty_string(self):
        assert _sanitize_id("") == ""

    def test_none_like_empty(self):
        assert _sanitize_id(None) == ""


# ─── _split_into_sentences ───────────────────────────────────────────────────

class TestSplitIntoSentences:
    def test_splits_on_period_capital(self):
        text = "He committed theft. The property was returned."
        parts = _split_into_sentences(text)
        assert len(parts) == 2
        assert parts[0] == "He committed theft."

    def test_splits_on_semicolon_capital(self):
        text = "Act one was done; Another act followed."
        parts = _split_into_sentences(text)
        assert len(parts) == 2

    def test_splits_before_lettered_clause(self):
        text = "A man commits rape if he (a) penetrates; or (b) inserts an object."
        parts = _split_into_sentences(text)
        # Should split before (a) and (b)
        assert any("(a)" in p for p in parts)
        assert any("(b)" in p for p in parts)

    def test_splits_before_numbered_clause(self):
        text = "The section states (1) first rule; and (2) second rule."
        parts = _split_into_sentences(text)
        assert any("(1)" in p for p in parts)
        assert any("(2)" in p for p in parts)

    def test_no_split_on_abbreviation(self):
        # "e.g." should not split since next char is not capital
        text = "Common offences e.g. theft are cognizable."
        parts = _split_into_sentences(text)
        # Should come back as a single sentence (no capital after period)
        assert len(parts) == 1

    def test_empty_string_returns_empty(self):
        assert _split_into_sentences("") == []

    def test_single_sentence_no_split(self):
        text = "Whoever commits murder shall be punished."
        parts = _split_into_sentences(text)
        assert len(parts) == 1
        assert parts[0] == text


# ─── _chunk_text ─────────────────────────────────────────────────────────────

class TestChunkText:
    def test_empty_returns_empty(self):
        assert _chunk_text("", 100, 20) == []

    def test_short_text_single_chunk(self):
        text = "Short legal provision. Another sentence."
        result = _chunk_text(text, chunk_size_words=500, overlap_words=50)
        assert len(result) == 1
        assert result[0] == text

    def test_chunks_do_not_split_mid_sentence(self):
        # Build text with sentences ≈ 30 words each, chunk at 50 words
        sentences = [
            "Whoever commits the offence of theft shall be punished with imprisonment which may extend to three years.",
            "The court may also impose a fine in addition to the sentence of imprisonment.",
            "Repeat offenders may face enhanced punishment under the provisions of this section.",
            "This section applies to all movable property taken without the owner's consent.",
        ]
        text = " ".join(sentences)
        chunks = _chunk_text(text, chunk_size_words=50, overlap_words=15)

        # Every chunk must start with the beginning of one of our sentences
        sentence_starts = {s.split()[0] for s in sentences}
        for chunk in chunks:
            first_word = chunk.split()[0]
            assert first_word in sentence_starts, (
                f"Chunk starts mid-sentence: '{chunk[:60]}'"
            )

    def test_overlap_carries_sentences(self):
        sentences = [
            "First sentence about theft of property.",
            "Second sentence about robbery with force.",
            "Third sentence about extortion and blackmail.",
            "Fourth sentence about house trespass and burglary.",
        ]
        text = " ".join(sentences)
        chunks = _chunk_text(text, chunk_size_words=15, overlap_words=8)
        # With a tight chunk size, later chunks should repeat some sentence from earlier
        if len(chunks) > 1:
            earlier_content = set(chunks[0].split())
            overlap_content = set(chunks[1].split())
            assert earlier_content & overlap_content, "Expected some overlap between consecutive chunks"

    def test_oversized_single_sentence_emitted_alone(self):
        long_sentence = " ".join(["word"] * 300)
        result = _chunk_text(long_sentence, chunk_size_words=100, overlap_words=20)
        assert len(result) == 1
        assert result[0] == long_sentence

    def test_none_text_returns_empty(self):
        assert _chunk_text(None, 100, 20) == []


# ─── _sections_from_csv ──────────────────────────────────────────────────────

class TestSectionsFromCsv:
    def _make_csv(self, rows: list[dict]) -> str:
        """Write rows to a temp CSV file and return the path."""
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".csv",
                                        delete=False, encoding="utf-8", newline="")
        fieldnames = list(rows[0].keys())
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
        f.close()
        return f.name

    def test_reads_standard_columns(self):
        path = self._make_csv([
            {"Section": "74", "Section _name": "Assault modesty", "Description": "Legal text here.", "plain_language": "molestation"},
        ])
        try:
            sections = _sections_from_csv(path)
            assert len(sections) == 1
            s = sections[0]
            assert s["section_number"] == "74"
            assert s["section_title"] == "Assault modesty"
            assert s["full_text"] == "Legal text here."
            assert s["plain_language"] == "molestation"
        finally:
            os.unlink(path)

    def test_skips_empty_rows(self):
        path = self._make_csv([
            {"Section": "", "Section _name": "", "Description": "", "plain_language": ""},
            {"Section": "1", "Section _name": "Title", "Description": "Text.", "plain_language": ""},
        ])
        try:
            sections = _sections_from_csv(path)
            assert len(sections) == 1
        finally:
            os.unlink(path)

    def test_missing_plain_language_defaults_empty(self):
        path = self._make_csv([
            {"Section": "303", "Section _name": "Theft", "Description": "Theft text."},
        ])
        try:
            sections = _sections_from_csv(path)
            assert sections[0]["plain_language"] == ""
        finally:
            os.unlink(path)

    def test_real_bns_csv(self, bns_csv_path):
        if not os.path.exists(bns_csv_path):
            pytest.skip("bns_augmented.csv not found")
        sections = _sections_from_csv(bns_csv_path)
        assert len(sections) == 358
        section_numbers = {s["section_number"] for s in sections}
        # All augmented critical sections must be present
        for sec in ["63", "74", "75", "85", "86", "109", "303", "308", "329"]:
            assert sec in section_numbers, f"Section {sec} missing from CSV"

    def test_augmented_sections_have_plain_language(self, bns_csv_path):
        if not os.path.exists(bns_csv_path):
            pytest.skip("bns_augmented.csv not found")
        sections = _sections_from_csv(bns_csv_path)
        by_number = {s["section_number"]: s for s in sections}

        expected = {
            "74": "molestation",
            "63": "rape",
            "303": "theft",
            "85": "cruelty",
            "308": "extortion",
        }
        for sec, keyword in expected.items():
            pl = by_number[sec]["plain_language"]
            assert keyword in pl, f"Section {sec} plain_language missing '{keyword}': {pl!r}"


# ─── build_chunks ─────────────────────────────────────────────────────────────

class TestBuildChunks:
    BASE_SECTION = {
        "act_name": "BNS",
        "section_number": "74",
        "section_title": "Assault modesty",
        "full_text": "Whoever assaults any woman. The offender shall be punished.",
        "plain_language": "molestation outrage modesty",
    }

    def test_first_chunk_contains_plain_language(self):
        chunks = build_chunks([self.BASE_SECTION])
        first = chunks[0]["document"]
        assert "also known as" in first
        assert "molestation" in first

    def test_subsequent_chunks_omit_plain_language(self):
        # Build a section long enough to produce multiple chunks
        long_text = ". ".join(
            [f"Sentence {idx} about legal provisions and punishments under this act"
             for idx in range(30)]
        )
        section = {**self.BASE_SECTION, "full_text": long_text}
        chunks = build_chunks([section])
        if len(chunks) > 1:
            for chunk in chunks[1:]:
                assert "also known as" not in chunk["document"]

    def test_no_plain_language_no_suffix(self):
        section = {**self.BASE_SECTION, "plain_language": ""}
        chunks = build_chunks([section])
        assert "also known as" not in chunks[0]["document"]

    def test_chunk_id_format(self):
        chunks = build_chunks([self.BASE_SECTION])
        assert chunks[0]["id"] == "BNS_74_0"

    def test_metadata_preserved(self):
        chunks = build_chunks([self.BASE_SECTION])
        meta = chunks[0]["metadata"]
        assert meta["act_name"] == "BNS"
        assert meta["section_number"] == "74"
        assert meta["section_title"] == "Assault modesty"
        assert meta["chunk_index"] == 0

    def test_document_prefix_includes_act_and_section(self):
        chunks = build_chunks([self.BASE_SECTION])
        doc = chunks[0]["document"]
        assert doc.startswith("BNS Section 74: Assault modesty.")

    def test_empty_sections_list(self):
        assert build_chunks([]) == []
