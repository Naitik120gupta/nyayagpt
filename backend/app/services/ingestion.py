import csv
import json
import logging
import os
import re
from typing import Dict, List

import chromadb

try:
    from backend.app.core.config import settings
    from backend.app.services.embeddings import InLegalBERTEmbeddingService
except ModuleNotFoundError as error:
    if not (error.name or "").startswith("backend"):
        raise
    from app.core.config import settings
    from app.services.embeddings import InLegalBERTEmbeddingService


logger = logging.getLogger(__name__)


def _sanitize_id(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_\-]", "_", (value or "").strip())


def _normalize_column_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (name or "").lower())


def _first_non_empty(record: dict, candidate_keys: List[str]) -> str:
    normalized = {_normalize_column_name(k): v for k, v in record.items() if k is not None}
    for key in candidate_keys:
        value = normalized.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


_SENTENCE_SPLIT_RE = re.compile(
    r"(?<=[.;])\s+(?=[A-Z\(\"])"   # period/semicolon → capital or open-paren
    r"|(?<=:)\s+(?=[A-Z\(\"])"      # colon → capital or open-paren
    r"|(?=\s+\([a-z]\)\s)"          # before lettered clause  (a) (b) …
    r"|(?=\s+\(\d+\)\s)"            # before numbered clause  (1) (2) …
)


def _split_into_sentences(text: str) -> List[str]:
    parts = _SENTENCE_SPLIT_RE.split(text.strip())
    return [p.strip() for p in parts if p.strip()]


def _chunk_text(text: str, chunk_size_words: int, overlap_words: int) -> List[str]:
    """Sentence-boundary-aware chunking.

    Accumulates sentences until the running word count would exceed
    *chunk_size_words*, then starts a new chunk with the last few sentences
    as context (overlap).  This keeps sentences intact and makes every chunk
    begin and end at a natural boundary.
    """
    sentences = _split_into_sentences(text or "")
    if not sentences:
        return []

    def _word_count(s: str) -> int:
        return len(s.split())

    chunks: List[str] = []
    current: List[str] = []
    current_words = 0

    for sentence in sentences:
        sw = _word_count(sentence)

        # If a single sentence exceeds the chunk size, emit it alone.
        if sw >= chunk_size_words:
            if current:
                chunks.append(" ".join(current))
                current, current_words = [], 0
            chunks.append(sentence)
            continue

        if current_words + sw > chunk_size_words and current:
            chunks.append(" ".join(current))
            # Carry-over: keep trailing sentences whose total ≤ overlap_words.
            overlap: List[str] = []
            overlap_total = 0
            for s in reversed(current):
                sw2 = _word_count(s)
                if overlap_total + sw2 <= overlap_words:
                    overlap.insert(0, s)
                    overlap_total += sw2
                else:
                    break
            current, current_words = overlap, overlap_total

        current.append(sentence)
        current_words += sw

    if current:
        chunks.append(" ".join(current))

    return chunks


def _sections_from_txt(raw_legal_text: str):
    section_pattern = re.compile(
        r"Section\s+([\w\-\.]+)\s*:\s*(.+?)\n(.+?)(?=\nSection\s+[\w\-\.]+\s*:|\Z)",
        re.DOTALL | re.IGNORECASE,
    )
    legal_sections = []
    for match in section_pattern.finditer(raw_legal_text):
        section_no = match.group(1).strip()
        title = match.group(2).strip()
        description = re.sub(r"\s+", " ", match.group(3).strip())
        legal_sections.append(
            {
                "act_name": "BNS",
                "section_number": section_no,
                "section_title": title,
                "full_text": description,
                "plain_language": "",
            }
        )
    return legal_sections


def _sections_from_csv(csv_path: str):
    legal_sections = []
    with open(csv_path, "r", encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        for index, row in enumerate(reader, start=1):
            section_no = _first_non_empty(
                row,
                [
                    "section",
                    "sectionno",
                    "sectionnumber",
                    "bnssection",
                    "bnssectionno",
                    "id",
                ],
            )
            title = _first_non_empty(
                row,
                ["sectionname", "sectiontitle", "title", "heading", "name", "offence", "offense"],
            )
            description = _first_non_empty(
                row,
                ["description", "text", "details", "content", "provision", "punishment"],
            )
            act_name = _first_non_empty(row, ["act", "actname", "law", "code", "chaptername"]) or "BNS"
            plain_language = _first_non_empty(row, ["plainlanguage", "plain_language", "synonyms", "keywords"])

            if not (section_no or title or description):
                continue

            legal_sections.append(
                {
                    "act_name": act_name,
                    "section_number": section_no or f"ROW-{index}",
                    "section_title": title or "Untitled",
                    "full_text": description or "",
                    "plain_language": plain_language,
                }
            )
    return legal_sections


def _sections_from_json(json_path: str):
    with open(json_path, "r", encoding="utf-8") as json_file:
        payload = json.load(json_file)

    records = payload if isinstance(payload, list) else payload.get("data", [])
    if not isinstance(records, list):
        raise ValueError("Unsupported JSON structure for legal dataset. Expected a list of section objects.")

    legal_sections = []
    for index, row in enumerate(records, start=1):
        if not isinstance(row, dict):
            continue

        section_no = _first_non_empty(
            row,
            [
                "section",
                "sectionno",
                "sectionnumber",
                "bnssection",
                "bnssectionno",
                "id",
            ],
        )
        title = _first_non_empty(
            row,
            ["sectionname", "sectiontitle", "title", "heading", "name", "offence", "offense"],
        )
        description = _first_non_empty(
            row,
            ["description", "text", "details", "content", "provision", "punishment"],
        )
        act_name = _first_non_empty(row, ["act", "actname", "law", "code", "chaptername"]) or "BNS"
        plain_language = _first_non_empty(row, ["plainlanguage", "plain_language", "synonyms", "keywords"])

        if not (section_no or title or description):
            continue

        legal_sections.append(
            {
                "act_name": act_name,
                "section_number": section_no or f"ROW-{index}",
                "section_title": title or "Untitled",
                "full_text": description or "",
                "plain_language": plain_language,
            }
        )

    return legal_sections


def load_legal_sections(data_path: str):
    if not os.path.exists(data_path):
        raise FileNotFoundError(f"Legal data file not found at {data_path}")

    extension = os.path.splitext(data_path)[1].lower()
    if extension == ".csv":
        return _sections_from_csv(data_path)
    if extension == ".json":
        return _sections_from_json(data_path)

    with open(data_path, "r", encoding="utf-8") as txt_file:
        return _sections_from_txt(txt_file.read())


def build_chunks(sections: List[Dict[str, str]]) -> List[Dict[str, object]]:
    chunked_rows: List[Dict[str, object]] = []
    for section in sections:
        act_name = section["act_name"]
        section_number = section["section_number"]
        section_title = section["section_title"]
        full_text = section["full_text"]
        plain_language = section.get("plain_language", "")

        chunks = _chunk_text(
            full_text,
            chunk_size_words=settings.INGEST_CHUNK_SIZE_WORDS,
            overlap_words=settings.INGEST_CHUNK_OVERLAP_WORDS,
        ) or [full_text]

        for chunk_index, chunk_text in enumerate(chunks):
            # Append plain-language synonyms to the first chunk only so the
            # embedding captures colloquial search terms without bloating every chunk.
            suffix = f" [also known as: {plain_language}]" if plain_language and chunk_index == 0 else ""
            document = f"{act_name} Section {section_number}: {section_title}. {chunk_text}{suffix}".strip()
            chunked_rows.append(
                {
                    "id": f"{_sanitize_id(act_name)}_{_sanitize_id(section_number)}_{chunk_index}",
                    "document": document,
                    "metadata": {
                        "act_name": act_name,
                        "section_number": str(section_number),
                        "section_title": section_title,
                        "full_text": full_text,
                        "chunk_index": chunk_index,
                    },
                }
            )

    return chunked_rows


def ingest_legal_corpus(data_path: str | None = None) -> int:
    target_data_path = data_path or settings.BNS_DATA_PATH
    logger.info("Loading legal corpus from %s", target_data_path)

    sections = load_legal_sections(target_data_path)
    if not sections:
        raise ValueError("No legal sections found in the input dataset.")

    chunk_rows = build_chunks(sections)
    if not chunk_rows:
        raise ValueError("No chunked documents generated from legal corpus.")

    embedding_service = InLegalBERTEmbeddingService()
    embeddings = embedding_service.embed_documents([row["document"] for row in chunk_rows])

    os.makedirs(settings.VECTOR_STORE_DIR, exist_ok=True)
    client = chromadb.PersistentClient(path=settings.VECTOR_STORE_DIR)

    try:
        existing = [collection.name for collection in client.list_collections()]
        if settings.COLLECTION_NAME in existing:
            client.delete_collection(settings.COLLECTION_NAME)
    except Exception as error:
        logger.warning("Collection cleanup warning: %s", error)

    collection = client.create_collection(
        name=settings.COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )
    collection.add(
        ids=[row["id"] for row in chunk_rows],
        documents=[row["document"] for row in chunk_rows],
        metadatas=[row["metadata"] for row in chunk_rows],
        embeddings=embeddings,
    )

    logger.info("Ingestion completed. Indexed %s chunks.", collection.count())
    return collection.count()
