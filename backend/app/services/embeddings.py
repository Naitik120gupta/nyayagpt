import hashlib
import json
import logging
import os
import sqlite3
import threading
from typing import Iterable, List

import numpy as np
from sentence_transformers import SentenceTransformer
from sentence_transformers.models import Normalize, Pooling, Transformer

try:
    from backend.app.core.config import settings
except ModuleNotFoundError:
    from app.core.config import settings


logger = logging.getLogger(__name__)


class InLegalBERTEmbeddingService:
    _instance = None
    _instance_lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return

        configured_device = (settings.EMBEDDING_DEVICE or "").strip().lower()
        if configured_device == "cuda":
            logger.warning("CUDA device setting is disabled; falling back to CPU.")
            self.device = "cpu"
        elif configured_device in {"cpu", "mps"}:
            self.device = configured_device
        else:
            self.device = "cpu"

        self.model_name = settings.LOCAL_EMBEDDING_MODEL
        self.batch_size = settings.EMBEDDING_BATCH_SIZE
        self.query_instruction = settings.QUERY_EMBEDDING_PREFIX or ""
        self.model_cache_dir = os.path.expanduser(settings.MODEL_CACHE_DIR)
        self.use_safetensors = settings.USE_SAFETENSORS

        os.makedirs(self.model_cache_dir, exist_ok=True)
        os.environ.setdefault("HF_HOME", self.model_cache_dir)
        os.environ.setdefault("TRANSFORMERS_CACHE", self.model_cache_dir)

        logger.info(
            "Loading embedding model %s on %s (use_safetensors=%s)",
            self.model_name,
            self.device,
            self.use_safetensors,
        )
        word_embedding_model = Transformer(
            self.model_name,
            cache_dir=self.model_cache_dir,
            model_args={"use_safetensors": self.use_safetensors},
        )
        pooling_model = Pooling(
            word_embedding_model.get_word_embedding_dimension(),
            pooling_mode_mean_tokens=True,
            pooling_mode_cls_token=False,
            pooling_mode_max_tokens=False,
        )
        normalize_model = Normalize()

        self.model = SentenceTransformer(
            modules=[word_embedding_model, pooling_model, normalize_model],
            device=self.device,
            cache_folder=self.model_cache_dir,
        )

        self.cache_path = settings.EMBEDDING_CACHE_PATH
        os.makedirs(os.path.dirname(self.cache_path), exist_ok=True)
        self._cache_lock = threading.Lock()
        self._init_cache()

        self._initialized = True

    def _init_cache(self):
        with sqlite3.connect(self.cache_path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS embedding_cache (
                    cache_key TEXT PRIMARY KEY,
                    vector_json TEXT NOT NULL
                )
                """
            )
            connection.commit()

    def _build_cache_key(self, text: str, mode: str) -> str:
        payload = f"{self.model_name}|{mode}|{text}".encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def _get_cached(self, cache_key: str):
        with self._cache_lock:
            with sqlite3.connect(self.cache_path) as connection:
                row = connection.execute(
                    "SELECT vector_json FROM embedding_cache WHERE cache_key = ?",
                    (cache_key,),
                ).fetchone()
        if not row:
            return None
        return json.loads(row[0])

    def _set_cached_many(self, entries: Iterable[tuple[str, List[float]]]):
        rows = [(cache_key, json.dumps(vector)) for cache_key, vector in entries]
        if not rows:
            return

        with self._cache_lock:
            with sqlite3.connect(self.cache_path) as connection:
                connection.executemany(
                    "INSERT OR REPLACE INTO embedding_cache (cache_key, vector_json) VALUES (?, ?)",
                    rows,
                )
                connection.commit()

    def _encode_uncached(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        embeddings = self.model.encode(
            texts,
            batch_size=self.batch_size,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return embeddings.astype(np.float32).tolist()

    def _embed(self, texts: List[str], mode: str) -> List[List[float]]:
        if not texts:
            return []

        prepared_texts = [t.strip() if t else "" for t in texts]
        cache_keys = [self._build_cache_key(t, mode) for t in prepared_texts]

        vectors: List[List[float] | None] = [None] * len(prepared_texts)
        misses_idx: List[int] = []
        misses_text: List[str] = []

        for index, key in enumerate(cache_keys):
            cached = self._get_cached(key)
            if cached is not None:
                vectors[index] = cached
            else:
                misses_idx.append(index)
                misses_text.append(prepared_texts[index])

        if misses_text:
            encoded = self._encode_uncached(misses_text)
            cache_entries = []
            for i, vector in enumerate(encoded):
                original_index = misses_idx[i]
                vectors[original_index] = vector
                cache_entries.append((cache_keys[original_index], vector))
            self._set_cached_many(cache_entries)

        return [vector for vector in vectors if vector is not None]

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return self._embed(texts, mode="document")

    def embed_query(self, query: str) -> List[float]:
        normalized_query = (query or "").strip()
        if not normalized_query:
            return []

        query_text = f"{self.query_instruction}{normalized_query}" if self.query_instruction else normalized_query
        vectors = self._embed([query_text], mode="query")
        return vectors[0] if vectors else []
