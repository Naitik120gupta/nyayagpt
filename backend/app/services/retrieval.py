import json
import logging
import re
from typing import Any, Dict, List

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

ENGLISH_QUERY_PATTERN = re.compile(r"^[A-Za-z0-9\s.,!?;:'\"()\[\]{}\-_/&%+*=<>@#$`~|\\]+$")


def _normalize_query(query: str) -> str:
    text = (query or "").strip()
    text = re.sub(r"\s+", " ", text)
    return text


def is_english(query: str) -> bool:
    text = _normalize_query(query)
    if not text:
        return False
    if not text.isascii():
        return False
    return bool(ENGLISH_QUERY_PATTERN.fullmatch(text))


class MultilingualLegalRetriever:
    def __init__(self):
        self.embedding_service = InLegalBERTEmbeddingService()
        self.client = chromadb.PersistentClient(path=settings.VECTOR_STORE_DIR)
        self.collection = self.client.get_or_create_collection(name=settings.COLLECTION_NAME)

    def retrieve(self, query: str, k: int = 5) -> Dict[str, Any]:
        if not is_english(query):
            raise ValueError("Only English queries are supported")

        normalized_query = _normalize_query(query)
        prefixed_query = f"legal query: {normalized_query}" if normalized_query else ""
        query_embedding = self.embedding_service.embed_query(prefixed_query)

        if not query_embedding:
            return {
                "query": query,
                "normalized_query": normalized_query,
                "prefixed_query": prefixed_query,
                "results": [],
            }

        raw_results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=k,
            include=["documents", "metadatas", "distances"],
        )

        documents = raw_results.get("documents", [[]])[0]
        metadatas = raw_results.get("metadatas", [[]])[0]
        distances = raw_results.get("distances", [[]])[0]
        ids = raw_results.get("ids", [[]])[0]

        results = []
        for index, document in enumerate(documents):
            metadata = metadatas[index] if index < len(metadatas) else {}
            distance = distances[index] if index < len(distances) else None
            item_id = ids[index] if index < len(ids) else None
            results.append(
                {
                    "id": item_id,
                    "document": document,
                    "metadata": metadata or {},
                    "distance": distance,
                }
            )

        return {
            "query": query,
            "normalized_query": normalized_query,
            "prefixed_query": prefixed_query,
            "results": results,
        }

    def evaluate_top_k(self, test_data: List[Dict[str, Any]], k: int = 5) -> Dict[str, Any]:
        if not test_data:
            return {
                "accuracy": 0.0,
                "total": 0,
                "correct": 0,
                "details": [],
            }

        correct = 0
        details = []

        for sample in test_data:
            query = sample.get("query", "")
            expected_section = str(sample.get("expected_section", "")).strip()

            if not is_english(query):
                raise ValueError(f"Only English queries are supported in evaluation. Invalid query: {query}")

            retrieval_payload = self.retrieve(query, k=k)
            retrieved_items = retrieval_payload.get("results", [])

            hit = False
            for item in retrieved_items:
                metadata = item.get("metadata", {}) or {}
                section_number = str(metadata.get("section_number", "")).strip()
                section_title = str(metadata.get("section_title", "")).strip().lower()
                document = str(item.get("document", "")).lower()

                if expected_section and (
                    section_number == expected_section
                    or f"section {expected_section}" in document
                    or expected_section.lower() in section_title
                ):
                    hit = True
                    break

            correct += 1 if hit else 0
            details.append(
                {
                    "query": query,
                    "normalized_query": retrieval_payload.get("normalized_query"),
                    "expected_section": expected_section,
                    "hit": hit,
                    "top_k_sections": [
                        {
                            "section_number": (item.get("metadata") or {}).get("section_number"),
                            "section_title": (item.get("metadata") or {}).get("section_title"),
                        }
                        for item in retrieved_items
                    ],
                }
            )

        total = len(test_data)
        accuracy = correct / total if total else 0.0

        return {
            "accuracy": accuracy,
            "total": total,
            "correct": correct,
            "k": k,
            "details": details,
        }


def load_test_data(test_data_path: str) -> List[Dict[str, Any]]:
    with open(test_data_path, "r", encoding="utf-8") as file:
        payload = json.load(file)

    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and isinstance(payload.get("samples"), list):
        return payload["samples"]
    return []
