import sys
import os

# Add the project root to sys.path to allow imports from backend.app
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

import chromadb
import re
import logging
import csv
import json
import time
from google import genai
from google.genai import types
from backend.app.core.config import settings

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)
EMBED_BATCH_SIZE = 100
EMBED_MAX_RETRIES = 6
EMBED_BASE_DELAY_SECONDS = 15


def _sanitize_id(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_\-]", "_", value.strip())


def _normalize_column_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def _first_non_empty(record: dict, candidate_keys: list[str]) -> str:
    normalized = {_normalize_column_name(k): v for k, v in record.items() if k is not None}
    for key in candidate_keys:
        value = normalized.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _sections_from_txt(raw_legal_text: str):
    section_pattern = re.compile(r"Section\s+([\w\-\.]+)\s*:\s*(.+?)\n(.+?)(?=\nSection\s+[\w\-\.]+\s*:|\Z)", re.DOTALL | re.IGNORECASE)
    legal_sections = []
    for match in section_pattern.finditer(raw_legal_text):
        section_no = match.group(1).strip()
        title = match.group(2).strip()
        description = re.sub(r"\s+", " ", match.group(3).strip())
        legal_sections.append({
            "id": f"bns_{_sanitize_id(section_no)}",
            "document": f"BNS Section {section_no}: {title}. {description}"
        })
    return legal_sections


def _sections_from_csv(csv_path: str):
    legal_sections = []
    with open(csv_path, "r", encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        for idx, row in enumerate(reader, start=1):
            section_no = _first_non_empty(row, [
                "section", "sectionno", "sectionnumber", "bnssection", "bnssectionno", "id"
            ])
            title = _first_non_empty(row, [
                "title", "heading", "name", "offence", "offense", "sectiontitle"
            ])
            description = _first_non_empty(row, [
                "description", "text", "details", "content", "provision", "punishment"
            ])

            if not (section_no or title or description):
                continue

            section_label = section_no or f"ROW-{idx}"
            body_parts = [part for part in [title, description] if part]
            body = ". ".join(body_parts) if body_parts else "No description provided"

            legal_sections.append({
                "id": f"bns_{_sanitize_id(section_label)}",
                "document": f"BNS Section {section_label}: {body}"
            })

    return legal_sections


def _sections_from_json(json_path: str):
    with open(json_path, "r", encoding="utf-8") as json_file:
        payload = json.load(json_file)

    records = payload if isinstance(payload, list) else payload.get("data", [])
    if not isinstance(records, list):
        raise ValueError("Unsupported JSON structure for BNS dataset. Expected a list of section objects.")

    legal_sections = []
    for idx, row in enumerate(records, start=1):
        if not isinstance(row, dict):
            continue

        section_no = _first_non_empty(row, [
            "section", "sectionno", "sectionnumber", "bnssection", "bnssectionno", "id"
        ])
        title = _first_non_empty(row, [
            "title", "heading", "name", "offence", "offense", "sectiontitle"
        ])
        description = _first_non_empty(row, [
            "description", "text", "details", "content", "provision", "punishment"
        ])

        if not (section_no or title or description):
            continue

        section_label = section_no or f"ROW-{idx}"
        body_parts = [part for part in [title, description] if part]
        body = ". ".join(body_parts) if body_parts else "No description provided"

        legal_sections.append({
            "id": f"bns_{_sanitize_id(section_label)}",
            "document": f"BNS Section {section_label}: {body}"
        })

    return legal_sections


def _load_legal_sections_from_dataset():
    data_path = settings.BNS_DATA_PATH
    logger.info(f"Loading data from {data_path}")

    if not os.path.exists(data_path):
        logger.error(f"BNS data file not found at {data_path}")
        return []

    extension = os.path.splitext(data_path)[1].lower()

    if extension == ".csv":
        return _sections_from_csv(data_path)
    if extension == ".json":
        return _sections_from_json(data_path)

    with open(data_path, "r", encoding="utf-8") as txt_file:
        raw_legal_text = txt_file.read()
    return _sections_from_txt(raw_legal_text)


def _is_quota_error(error: Exception) -> bool:
    message = str(error).lower()
    return "429" in message or "resource_exhausted" in message or "quota" in message


def _embed_batch_with_retry(client, batch_documents):
    last_error = None
    for attempt in range(1, EMBED_MAX_RETRIES + 1):
        try:
            result = client.models.embed_content(
                model=settings.EMBEDDING_MODEL,
                contents=batch_documents,
                config=types.EmbedContentConfig(task_type="RETRIEVAL_DOCUMENT")
            )
            return [e.values for e in result.embeddings]
        except Exception as error:
            last_error = error
            if not _is_quota_error(error) or attempt == EMBED_MAX_RETRIES:
                raise

            sleep_seconds = EMBED_BASE_DELAY_SECONDS * attempt
            logger.warning(
                "Embedding quota hit (attempt %s/%s). Retrying in %s seconds...",
                attempt,
                EMBED_MAX_RETRIES,
                sleep_seconds,
            )
            time.sleep(sleep_seconds)

    if last_error:
        raise last_error

def main():
    logger.info("--- Starting Data Ingestion ---")

    # Configure Gemini API
    if not settings.GEMINI_API_KEY:
        logger.error("GEMINI_API_KEY not found in configuration.")
        return
    client = genai.Client(api_key=settings.GEMINI_API_KEY)

    # 1. Load + Parse Data
    legal_sections = _load_legal_sections_from_dataset()
    if not legal_sections:
        logger.error("No valid BNS sections were parsed from dataset.")
        return

    unique_sections = []
    seen_ids = set()
    for section in legal_sections:
        section_id = section["id"]
        if section_id in seen_ids:
            continue
        seen_ids.add(section_id)
        unique_sections.append(section)
    legal_sections = unique_sections

    logger.info(f"Parsed {len(legal_sections)} sections.")

    # 3. Create Embeddings with Gemini API
    logger.info(f"Generating embeddings with Gemini model: {settings.EMBEDDING_MODEL}...")
    try:
        embeddings = []
        for batch_start in range(0, len(legal_sections), EMBED_BATCH_SIZE):
            batch = legal_sections[batch_start:batch_start + EMBED_BATCH_SIZE]
            batch_embeddings = _embed_batch_with_retry(
                client,
                [s['document'] for s in batch]
            )
            embeddings.extend(batch_embeddings)

        if len(embeddings) != len(legal_sections):
            raise ValueError(
                f"Embedding count mismatch: got {len(embeddings)} vectors for {len(legal_sections)} sections"
            )

        logger.info("Embeddings generated successfully.")
    except Exception as e:
        logger.error(f"Failed to generate embeddings with Gemini API: {e}")
        return

    # 4. Initialize and Populate Vector DB
    # Create directory if it doesn't exist
    os.makedirs(settings.VECTOR_STORE_DIR, exist_ok=True)
    logger.info(f"Vector Store Path: {settings.VECTOR_STORE_DIR}")

    chroma_client = chromadb.PersistentClient(path=settings.VECTOR_STORE_DIR)

    # Check if collection exists and delete it
    try:
         # List collections returns objects, need to check names
         collections = chroma_client.list_collections()
         if any(c.name == settings.COLLECTION_NAME for c in collections):
             chroma_client.delete_collection(name=settings.COLLECTION_NAME)
    except Exception as e:
        logger.warning(f"Warning during collection deletion: {e}")

    vector_collection = chroma_client.create_collection(name=settings.COLLECTION_NAME)
    vector_collection.add(
        embeddings=embeddings,
        documents=[s['document'] for s in legal_sections],
        ids=[s['id'] for s in legal_sections]
    )

    logger.info(f"Successfully added {vector_collection.count()} documents to the vector store.")
    logger.info("--- Data Ingestion Complete ---")

if __name__ == "__main__":
    main()
