import chromadb
import re
import os
import google.generativeai as genai
from dotenv import load_dotenv

# --- Configuration ---
load_dotenv()
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
VECTOR_STORE_PATH = os.path.join(CURRENT_DIR, "vector_store")
DATA_PATH = os.path.join(CURRENT_DIR, "data", "ipc_data.txt")
COLLECTION_NAME = "indian_penal_code"
EMBEDDING_MODEL = "models/embedding-001"

def main():
    print("--- Starting Data Ingestion ---")
    
    # Configure Gemini API
    api_key = os.environ.get('GEMINI_API_KEY')
    if not api_key:
        print("ERROR: GEMINI_API_KEY not found in .env file.")
        return
    genai.configure(api_key=api_key)

    # 1. Load Data
    try:
        with open(DATA_PATH, 'r', encoding='utf-8') as f:
            raw_legal_text = f.read()
    except FileNotFoundError:
        print(f"ERROR: Data file not found at {DATA_PATH}")
        return

    # 2. Parse Data
    section_pattern = re.compile(r"Section (\d+): (.+?)\n(.+?)(?=\nSection|\Z)", re.DOTALL)
    legal_sections = [{"id": f"ipc_{m.group(1).strip()}", "document": f"Section {m.group(1).strip()}: {m.group(2).strip()}. {m.group(3).strip().replace(chr(10), ' ')}"} for m in section_pattern.finditer(raw_legal_text)]
    
    print(f"Parsed {len(legal_sections)} sections.")
    
    # 3. Create Embeddings with Gemini API
    print(f"Generating embeddings with Gemini model: {EMBEDDING_MODEL}...")
    try:
        embedding_result = genai.embed_content(
            model=EMBEDDING_MODEL,
            content=[s['document'] for s in legal_sections],
            task_type="retrieval_document"
        )
        embeddings = embedding_result['embedding']
        print("Embeddings generated successfully.")
    except Exception as e:
        print(f"ERROR: Failed to generate embeddings with Gemini API: {e}")
        return

    # 4. Initialize and Populate Vector DB
    chroma_client = chromadb.PersistentClient(path=VECTOR_STORE_PATH)
    if COLLECTION_NAME in [c.name for c in chroma_client.list_collections()]:
        chroma_client.delete_collection(name=COLLECTION_NAME)
    
    vector_collection = chroma_client.create_collection(name=COLLECTION_NAME)
    vector_collection.add(
        embeddings=embeddings,
        documents=[s['document'] for s in legal_sections],
        ids=[s['id'] for s in legal_sections]
    )
    
    print(f"Successfully added {vector_collection.count()} documents to the vector store.")
    print("--- Data Ingestion Complete ---")

if __name__ == "__main__":
    main()
