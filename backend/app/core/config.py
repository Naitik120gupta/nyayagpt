import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    PROJECT_NAME: str = "Nyay Sahayak"

    # Paths
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    VECTOR_STORE_DIR = os.path.join(BASE_DIR, "vector_store")
    DATA_DIR = os.path.join(BASE_DIR, "data")
    IPC_DATA_PATH = os.path.join(DATA_DIR, "ipc_data.txt")

    # Gemini
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    EMBEDDING_MODEL = "models/embedding-001"
    GENERATION_MODEL = "gemini-1.5-flash-latest"

    # ChromaDB
    COLLECTION_NAME = "indian_penal_code"

settings = Settings()
