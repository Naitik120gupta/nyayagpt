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

    # Gemini
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    EMBEDDING_MODEL = "models/gemini-embedding-001"
    GENERATION_MODEL = "models/gemini-2.5-flash"

    # ChromaDB
    COLLECTION_NAME = "bharatiya_nyaya_sanhita"

settings = Settings()
