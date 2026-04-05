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


def _chunk_text(text: str, chunk_size_words: int, overlap_words: int) -> List[str]:
    words = (text or "").split()
    if not words:
        return []
    if len(words) <= chunk_size_words:
        return [" ".join(words)]

    chunks = []
    step = max(1, chunk_size_words - overlap_words)
    for start in range(0, len(words), step):
        chunk = words[start : start + chunk_size_words]
        if not chunk:
            continue
        chunks.append(" ".join(chunk))
        if start + chunk_size_words >= len(words):
            break
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

            if not (section_no or title or description):
                continue

            legal_sections.append(
                {
                    "act_name": act_name,
                    "section_number": section_no or f"ROW-{index}",
                    "section_title": title or "Untitled",
                    "full_text": description or "",
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

        if not (section_no or title or description):
            continue

        legal_sections.append(
            {
                "act_name": act_name,
                "section_number": section_no or f"ROW-{index}",
                "section_title": title or "Untitled",
                "full_text": description or "",
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

        chunks = _chunk_text(
            full_text,
            chunk_size_words=settings.INGEST_CHUNK_SIZE_WORDS,
            overlap_words=settings.INGEST_CHUNK_OVERLAP_WORDS,
        ) or [full_text]

        for chunk_index, chunk_text in enumerate(chunks):
            document = f"{act_name} Section {section_number}: {section_title}. {chunk_text}".strip()
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

    collection = client.create_collection(name=settings.COLLECTION_NAME)
    collection.add(
        ids=[row["id"] for row in chunk_rows],
        documents=[row["document"] for row in chunk_rows],
        metadatas=[row["metadata"] for row in chunk_rows],
        embeddings=embeddings,
    )

    logger.info("Ingestion completed. Indexed %s chunks.", collection.count())
    return collection.count()
