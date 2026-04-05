import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    PROJECT_NAME: str = "Nyay Sahayak"

    # Paths
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    VECTOR_STORE_DIR = os.path.join(BASE_DIR, "vector_store")
    DATA_DIR = os.path.join(BASE_DIR, "data")
    BNS_DATA_PATH = os.getenv("BNS_DATA_PATH", os.path.join(DATA_DIR, "bns_data.csv"))

    # Gemini (generation only)
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    GENERATION_MODEL = "models/gemini-2.5-flash"

    # Local Embeddings (InLegalBERT)
    LOCAL_EMBEDDING_MODEL = os.getenv("LOCAL_EMBEDDING_MODEL", "law-ai/InLegalBERT")
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

    # ChromaDB
    COLLECTION_NAME = "bharatiya_nyaya_sanhita"

settings = Settings()
