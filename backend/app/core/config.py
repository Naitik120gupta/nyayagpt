import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    PROJECT_NAME: str = "Nyay Sahayak"

    # Paths
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    VECTOR_STORE_DIR = os.path.join(BASE_DIR, "vector_store")
    DATA_DIR = os.path.join(BASE_DIR, "data")
    BNS_DATA_PATH = os.getenv("BNS_DATA_PATH", os.path.join(DATA_DIR, "bns_augmented.csv"))

    # Gemini (generation only)
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    GENERATION_MODEL = "gemini-2.5-flash"
    FALLBACK_GENERATION_MODEL = os.getenv("FALLBACK_GENERATION_MODEL", "models/gemini-1.5-pro")
    GEMINI_MAX_RETRIES = int(os.getenv("GEMINI_MAX_RETRIES", "3"))
    GEMINI_RETRY_BASE_DELAY = float(os.getenv("GEMINI_RETRY_BASE_DELAY", "2.0"))
    GEMINI_CACHE_PATH = os.getenv(
        "GEMINI_CACHE_PATH",
        os.path.join(VECTOR_STORE_DIR, "gemini_cache.sqlite3"),
    )
    # 0 = never expire
    GEMINI_CACHE_TTL_SECONDS = int(os.getenv("GEMINI_CACHE_TTL_SECONDS", "86400"))

    # Local Embeddings (InLegalBERT)
    LOCAL_EMBEDDING_MODEL = os.getenv("LOCAL_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
    EMBEDDING_DEVICE = os.getenv("EMBEDDING_DEVICE", "")
    EMBEDDING_BATCH_SIZE = int(os.getenv("EMBEDDING_BATCH_SIZE", "64"))
    QUERY_EMBEDDING_PREFIX = os.getenv("QUERY_EMBEDDING_PREFIX", "")
    MODEL_CACHE_DIR = os.getenv(
        "MODEL_CACHE_DIR",
        os.getenv("HF_HOME", os.path.expanduser("~/.cache/huggingface")),
    )
    USE_SAFETENSORS = os.getenv("USE_SAFETENSORS", "true").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    EMBEDDING_CACHE_PATH = os.getenv(
        "EMBEDDING_CACHE_PATH",
        os.path.join(VECTOR_STORE_DIR, "embedding_cache.sqlite3"),
    )

    # Ingestion chunking
    INGEST_CHUNK_SIZE_WORDS = int(os.getenv("INGEST_CHUNK_SIZE_WORDS", "220"))
    INGEST_CHUNK_OVERLAP_WORDS = int(os.getenv("INGEST_CHUNK_OVERLAP_WORDS", "40"))

    # Retrieval
    RETRIEVAL_TOP_K = int(os.getenv("RETRIEVAL_TOP_K", "5"))
    # Minimum cosine-similarity score to keep a result (score = 1 − distance).
    # Set to 0.0 to disable the threshold.
    MIN_RELEVANCE_SCORE = float(os.getenv("MIN_RELEVANCE_SCORE", "0.72"))

    # ChromaDB
    COLLECTION_NAME = "bharatiya_nyaya_sanhita"

settings = Settings()
