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
            raw_ipc_text = f.read()
    except FileNotFoundError:
        print(f"ERROR: Data file not found at {DATA_PATH}")
        return

    # 2. Parse Data
    pattern = re.compile(r"Section (\d+): (.+?)\n(.+?)(?=\nSection|\Z)", re.DOTALL)
    sections = [{"id": f"ipc_{m.group(1).strip()}", "document": f"Section {m.group(1).strip()}: {m.group(2).strip()}. {m.group(3).strip().replace(chr(10), ' ')}"} for m in pattern.finditer(raw_ipc_text)]
    
    print(f"Parsed {len(sections)} sections.")
    
    # 3. Create Embeddings with Gemini API
    print(f"Generating embeddings with Gemini model: {EMBEDDING_MODEL}...")
    try:
        result = genai.embed_content(
            model=EMBEDDING_MODEL,
            content=[s['document'] for s in sections],
            task_type="retrieval_document"
        )
        embeddings = result['embedding']
        print("Embeddings generated successfully.")
    except Exception as e:
        print(f"ERROR: Failed to generate embeddings with Gemini API: {e}")
        return

    # 4. Initialize and Populate Vector DB
    client = chromadb.PersistentClient(path=VECTOR_STORE_PATH)
    if COLLECTION_NAME in [c.name for c in client.list_collections()]:
        client.delete_collection(name=COLLECTION_NAME)
    
    collection = client.create_collection(name=COLLECTION_NAME)
    collection.add(
        embeddings=embeddings,
        documents=[s['document'] for s in sections],
        ids=[s['id'] for s in sections]
    )
    
    print(f"Successfully added {collection.count()} documents to the vector store.")
    print("--- Data Ingestion Complete ---")

if __name__ == "__main__":
    main()
