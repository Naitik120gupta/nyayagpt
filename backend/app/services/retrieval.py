import json
import logging
import math
from collections import Counter, defaultdict
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

# Weight of an injected legal synonym relative to a term the user typed.
_SYNONYM_WEIGHT = 0.6
# Section titles are short and highly informative, so they count extra in BM25.
_TITLE_BOOST = 2

ENGLISH_QUERY_PATTERN = re.compile(r"^[A-Za-z0-9\s.,!?;:'\"()\[\]{}\-_/&%+*=<>@#$`~|\\]+$")


def _normalize_query(query: str) -> str:
    text = (query or "").strip()
    text = re.sub(r"\s+", " ", text)
    return text
_STOPWORDS = frozenset({
    "a", "an", "the", "and", "or", "but", "if", "then", "of", "for", "to",
    "in", "on", "at", "by", "with", "from", "into", "onto", "as", "is",
    "was", "were", "be", "been", "being", "am", "are", "do", "does", "did",
    "has", "have", "had", "having", "will", "would", "shall", "should",
    "can", "could", "may", "might", "must", "i", "me", "my", "mine",
    "you", "your", "yours", "he", "him", "his", "she", "her", "hers",
    "it", "its", "we", "us", "our", "ours", "they", "them", "their",
    "theirs", "this", "that", "these", "those", "who", "whom", "whose",
    "which", "what", "when", "where", "why", "how", "there", "here",
    "someone", "somebody", "anyone", "anybody", "no", "not", "than", "so",
    "very", "just", "also", "such", "any", "some", "all", "each", "every",
    "other", "another", "same", "own", "about", "against",
})

_STEM_SUFFIXES = (
    "ations", "ation", "ments", "ment", "ingly", "ings", "ing", "edly", "ed", "ies", "s",
)


def _stem(token: str) -> str:
    """Light suffix-stripping stemmer so that e.g. "molested", "molestation" and
    "molest", or "threatened" and "threatens", match the same BM25 term."""
    if token.isdigit() or len(token) <= 3:
        return token
    for suffix in _STEM_SUFFIXES:
        if token.endswith(suffix) and len(token) - len(suffix) >= 3:
            if suffix == "s" and token.endswith(("ss", "us", "is")):
                break
            token = token[: -len(suffix)] + ("y" if suffix == "ies" else "")
            break
    if len(token) >= 4 and token[-1] == token[-2] and token[-1] not in "lsz":
        token = token[:-1]  # robbed -> robb -> rob, kidnapped -> kidnapp -> kidnap
    if len(token) > 4 and token.endswith("e"):
        token = token[:-1]  # house/houses -> hous
    return token


def _tokenize_text(text: str) -> List[str]:
    tokens = re.findall(r"[A-Za-z0-9]+", (text or "").lower())
    return [_stem(t) for t in tokens if t not in _STOPWORDS]


# Everyday words people use to describe an incident, mapped to the vocabulary
# the BNS text actually uses. Applied to the BM25 query only, so a victim's
# description ("my phone was stolen") can match the statute ("theft").
_LEGAL_SYNONYMS: Dict[str, str] = {
    "steal": "theft", "stole": "theft", "stolen": "theft stolen property", "thief": "theft",
    "thieves": "theft", "pickpocket": "theft", "shoplift": "theft",
    "snatch": "snatching theft", "grab": "snatching criminal force",
    "rob": "robbery", "robbed": "robbery", "mug": "robbery", "loot": "robbery dacoity",
    "gang": "dacoity robbers organised", "armed": "deadly weapon",
    "knife": "deadly weapon", "knifepoint": "deadly weapon robbery", "gun": "deadly weapon firearm",
    "gunpoint": "deadly weapon robbery", "shoot": "firearm murder", "shot": "firearm murder",
    "burglary": "house-breaking house-trespass", "burgle": "house-breaking house-trespass",
    "break": "house-breaking", "broke": "house-breaking", "enter": "trespass", "entered": "trespass",
    "intrude": "trespass", "intruder": "trespass",
    "cheat": "cheating", "cheated": "cheating", "fraud": "cheating dishonestly",
    "scam": "cheating", "con": "cheating", "duped": "cheating", "fake": "false counterfeit",
    "pretend": "personation", "pretended": "personation", "impersonate": "personation",
    "misuse": "breach trust misappropriation", "misused": "breach trust misappropriation",
    "embezzle": "breach trust misappropriation", "trusted": "entrusted",
    "forge": "forgery", "forged": "forgery", "signature": "forgery document",
    "threat": "criminal intimidation", "threaten": "criminal intimidation",
    "threatening": "criminal intimidation", "threatened": "criminal intimidation",
    "blackmail": "extortion", "demand": "extortion", "demanded": "extortion",
    "ransom": "kidnapping abduction ransom",
    "molest": "outrage modesty criminal force woman", "molested": "outrage modesty criminal force woman",
    "grope": "outrage modesty criminal force woman", "groped": "outrage modesty criminal force woman",
    "eve": "sexual harassment", "teasing": "sexual harassment",
    "lewd": "sexual harassment obscene", "obscene": "obscene", "sexual": "sexual",
    "stalk": "stalking", "stalking": "stalking", "follow": "stalking", "following": "stalking",
    "record": "voyeurism capture image", "recorded": "voyeurism capture image",
    "video": "voyeurism image", "photo": "voyeurism image", "spy": "voyeurism",
    "disrobe": "disrobe naked", "strip": "disrobe naked", "clothes": "disrobe",
    "rape": "rape", "raped": "rape",
    "dowry": "dowry cruelty", "husband": "cruelty husband", "inlaws": "cruelty relative husband",
    "beat": "hurt voluntarily causing hurt", "beaten": "hurt voluntarily causing hurt",
    "hit": "hurt assault", "slap": "hurt assault criminal force", "slapped": "hurt assault criminal force",
    "punch": "hurt assault", "punched": "hurt assault", "kick": "hurt assault",
    "attack": "assault hurt", "attacked": "assault hurt", "injure": "hurt", "injured": "hurt",
    "fracture": "grievous hurt", "broken": "grievous hurt", "rod": "dangerous weapon",
    "acid": "acid grievous hurt",
    "kill": "murder death", "killed": "murder death", "murdered": "murder",
    "careless": "negligence rash", "negligent": "negligence", "accident": "negligence rash",
    "rashly": "rash", "speeding": "rash driving",
    "kidnap": "kidnapping abduction", "kidnapped": "kidnapping abduction", "abduct": "abduction",
    "locked": "wrongful confinement", "confined": "wrongful confinement",
    "blocked": "wrongful restraint", "stopped": "wrongful restraint",
    "suicide": "abetment suicide",
    "rumour": "defamation imputation reputation", "rumours": "defamation imputation reputation",
    "reputation": "defamation", "slander": "defamation", "libel": "defamation",
    "bribe": "bribery gratification",
    "fire": "fire mischief", "burn": "fire mischief", "vandalise": "mischief", "damage": "mischief",
    "mob": "rioting unlawful assembly", "riot": "rioting",
    "currency": "counterfeit currency-notes", "notes": "currency-notes",
    "lie": "false evidence", "lied": "false evidence", "perjury": "false evidence",
    "traffic": "trafficking", "trafficked": "trafficking", "labour": "exploitation",
    "dog": "animal", "cat": "animal", "cow": "animal", "pet": "animal",
}
_STEMMED_LEGAL_SYNONYMS: Dict[str, List[str]] = {}
for _word, _expansion in _LEGAL_SYNONYMS.items():
    _expansions = _STEMMED_LEGAL_SYNONYMS.setdefault(_stem(_word), [])
    _expansions.extend(term for term in _tokenize_text(_expansion) if term not in _expansions)


def _expand_query_terms(query: str) -> Counter:
    """BM25 query terms: the query's own terms plus legal-vocabulary expansions.

    Expansion terms get a lower weight than words the user actually typed."""
    typed_tokens = _tokenize_text(query)
    terms: Counter = Counter(typed_tokens)
    for token in typed_tokens:
        for expansion in _STEMMED_LEGAL_SYNONYMS.get(token, []):
            if expansion not in typed_tokens:
                terms[expansion] = max(terms[expansion], _SYNONYM_WEIGHT)
    return terms


def _normalize_scores(scores: List[float]) -> List[float]:
    if not scores:
        return []

    maximum = max(scores)
    minimum = min(scores)
    if math.isclose(maximum, minimum):
        return [1.0 if score > 0 else 0.0 for score in scores]

    denominator = maximum - minimum
    return [(score - minimum) / denominator for score in scores]


def _combine_modalities(vector_score: float, bm25_score: float) -> float:
    """Weighted sum of the two normalized scores.

    A probabilistic OR (1 - (1-v)(1-b)) let the vector side dominate: raw BERT
    cosine similarities sit around 0.8-0.95 for almost every chunk, so every
    candidate scored high and keyword evidence barely moved the ranking."""
    vector_component = max(0.0, min(1.0, vector_score))
    bm25_component = max(0.0, min(1.0, bm25_score))
    vector_weight = max(0.0, min(1.0, settings.HYBRID_VECTOR_WEIGHT))
    return vector_weight * vector_component + (1.0 - vector_weight) * bm25_component


def _section_key(candidate: Dict[str, Any]) -> str:
    metadata = candidate.get("metadata") or {}
    section_number = str(metadata.get("section_number", "")).strip()
    if section_number:
        return f"{metadata.get('act_name', '')}::{section_number}"
    return str(candidate.get("id") or candidate.get("document", ""))


class _BM25Index:
    def __init__(self, records: List[Dict[str, Any]], k1: float = 1.5, b: float = 0.75):
        self.records = records
        self.k1 = k1
        self.b = b
        self.document_count = len(records)
        self.document_lengths: List[int] = []
        self.average_document_length = 0.0
        self.document_frequencies: Counter[str] = Counter()
        self.postings = defaultdict(list)

        if not records:
            return

        total_length = 0
        for index, record in enumerate(records):
            title = str((record.get("metadata") or {}).get("section_title", ""))
            tokens = _tokenize_text(str(record.get("document", ""))) + _tokenize_text(title) * _TITLE_BOOST
            term_frequencies = Counter(tokens)
            document_length = len(tokens)
            self.document_lengths.append(document_length)
            total_length += document_length

            for term in term_frequencies:
                self.document_frequencies[term] += 1
            for term, frequency in term_frequencies.items():
                self.postings[term].append((index, frequency))

        self.average_document_length = total_length / self.document_count if self.document_count else 0.0

    def score(self, query: str) -> List[float]:
        if not self.records or not query:
            return []

        query_terms = _expand_query_terms(query)
        if not query_terms:
            return [0.0 for _ in self.records]

        scores = [0.0 for _ in self.records]
        average_length = self.average_document_length or 1.0

        for term, query_frequency in query_terms.items():
            postings = self.postings.get(term)
            if not postings:
                continue

            document_frequency = self.document_frequencies.get(term, 0)
            if document_frequency <= 0:
                continue

            inverse_document_frequency = math.log(
                1.0 + ((self.document_count - document_frequency + 0.5) / (document_frequency + 0.5))
            )
            query_weight = ((query_frequency * 2.0) / (query_frequency + 1.0)) if query_frequency > 0 else 1.0

            for document_index, term_frequency in postings:
                document_length = self.document_lengths[document_index] or 1
                denominator = term_frequency + self.k1 * (1.0 - self.b + self.b * (document_length / average_length))
                if denominator <= 0:
                    continue
                scores[document_index] += (
                    inverse_document_frequency
                    * ((term_frequency * (self.k1 + 1.0)) / denominator)
                    * query_weight
                )

        return scores


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
        self._search_records = self._load_search_records()
        self._bm25_index = _BM25Index(self._search_records)

    def _load_search_records(self) -> List[Dict[str, Any]]:
        try:
            raw_records = self.collection.get(include=["documents", "metadatas"])
        except Exception as error:
            logger.warning("Unable to load BM25 corpus from vector store: %s", error)
            return []

        if not isinstance(raw_records, dict):
            return []

        documents = raw_records.get("documents", []) or []
        metadatas = raw_records.get("metadatas", []) or []
        ids = raw_records.get("ids", []) or []

        records: List[Dict[str, Any]] = []
        for index, document in enumerate(documents):
            if not document:
                continue
            records.append(
                {
                    "id": ids[index] if index < len(ids) else None,
                    "document": document,
                    "metadata": metadatas[index] if index < len(metadatas) else {},
                }
            )

        return records

    def _collect_vector_candidates(self, query_embedding: List[float], k: int) -> List[Dict[str, Any]]:
        candidate_pool_size = max(k * 10, 100)
        raw_results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=candidate_pool_size,
            include=["documents", "metadatas", "distances"],
        )

        documents = raw_results.get("documents", [[]])[0]
        metadatas = raw_results.get("metadatas", [[]])[0]
        distances = raw_results.get("distances", [[]])[0]
        ids = raw_results.get("ids", [[]])[0]

        similarities = [
            (1.0 - distances[index]) if index < len(distances) and distances[index] is not None else 1.0
            for index in range(len(documents))
        ]
        # Rescale within the candidate pool so the best vector match gets 1.0 and
        # the weakest 0.0; raw similarities are too compressed to compare with BM25.
        normalized_similarities = _normalize_scores(similarities)

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
                    "vector_similarity": similarities[index],
                    "vector_score": normalized_similarities[index],
                    "bm25_score": 0.0,
                }
            )

        return results

    def _collect_bm25_candidates(self, normalized_query: str) -> List[Dict[str, Any]]:
        bm25_scores = self._bm25_index.score(normalized_query)
        if not bm25_scores:
            return []

        normalized_bm25_scores = _normalize_scores(bm25_scores)
        results = []
        for index, normalized_bm25_score in enumerate(normalized_bm25_scores):
            if normalized_bm25_score <= 0:
                continue

            record = self._search_records[index]
            results.append(
                {
                    "id": record.get("id"),
                    "document": record.get("document", ""),
                    "metadata": record.get("metadata", {}) or {},
                    "distance": None,
                    "vector_score": 0.0,
                    "bm25_score": normalized_bm25_score,
                }
            )

        return results

    def _merge_candidates(self, vector_candidates: List[Dict[str, Any]], bm25_candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        candidates_by_key: Dict[str, Dict[str, Any]] = {}

        def _candidate_key(candidate: Dict[str, Any]) -> str:
            item_id = candidate.get("id")
            if item_id:
                return str(item_id)
            document = str(candidate.get("document", ""))
            return f"doc::{document}"

        for candidate in vector_candidates:
            candidates_by_key[_candidate_key(candidate)] = dict(candidate)

        for candidate in bm25_candidates:
            key = _candidate_key(candidate)
            existing = candidates_by_key.get(key)
            if existing is None:
                candidates_by_key[key] = dict(candidate)
                continue

            existing["bm25_score"] = max(float(existing.get("bm25_score", 0.0)), float(candidate.get("bm25_score", 0.0)))
            if not existing.get("metadata") and candidate.get("metadata"):
                existing["metadata"] = candidate.get("metadata")
            if not existing.get("document") and candidate.get("document"):
                existing["document"] = candidate.get("document")

        merged_candidates = list(candidates_by_key.values())
        for candidate in merged_candidates:
            candidate["score"] = _combine_modalities(
                float(candidate.get("vector_score", 0.0)),
                float(candidate.get("bm25_score", 0.0)),
            )

        merged_candidates.sort(
            key=lambda item: (
                float(item.get("score", 0.0)),
                float(item.get("vector_score", 0.0)),
                float(item.get("bm25_score", 0.0)),
            ),
            reverse=True,
        )

        # Several chunks of one long section can all match; keep only the best
        # one so the top-k holds k distinct sections instead of near-duplicates.
        best_per_section: Dict[str, Dict[str, Any]] = {}
        for candidate in merged_candidates:
            best_per_section.setdefault(_section_key(candidate), candidate)
        return list(best_per_section.values())

    def retrieve(self, query: str, k: int = 5) -> Dict[str, Any]:
        if not is_english(query):
            raise ValueError("Only English queries are supported")

        normalized_query = _normalize_query(query)
        if not normalized_query:
            return {
                "query": query,
                "normalized_query": normalized_query,
                "results": [],
            }

        query_embedding = self.embedding_service.embed_query(normalized_query)
        vector_candidates: List[Dict[str, Any]] = []
        if query_embedding:
            vector_candidates = self._collect_vector_candidates(query_embedding, k)

        bm25_candidates = self._collect_bm25_candidates(normalized_query)

        if not vector_candidates and not bm25_candidates:
            return {
                "query": query,
                "normalized_query": normalized_query,
                "results": [],
            }

        results = self._merge_candidates(vector_candidates, bm25_candidates)

        if not results:
            raise ValueError(
                "No relevant BNS sections were found in the hybrid search index for this query. "
                "Please re-ingest the legal dataset and try again."
            )

        thresholded_results = [
            result for result in results if result.get("score", 1.0) >= settings.MIN_RELEVANCE_SCORE
        ]

        if thresholded_results:
            selected_results = thresholded_results[:k]
        else:
            fallback_size = min(3, len(results))
            selected_results = results[:fallback_size]
            logger.warning(
                "Retrieval threshold %.2f filtered all hybrid candidates for query '%s'. "
                "Falling back to top %s raw matches.",
                settings.MIN_RELEVANCE_SCORE,
                normalized_query,
                fallback_size,
            )

        return {
            "query": query,
            "normalized_query": normalized_query,
            "results": selected_results,
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
