import chromadb
import google.generativeai as genai
import os
import traceback
from dotenv import load_dotenv

# --- Configuration ---
load_dotenv()
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
VECTOR_STORE_PATH = os.path.join(CURRENT_DIR, "vector_store")
COLLECTION_NAME = "indian_penal_code"
EMBEDDING_MODEL = "models/embedding-001"
GENERATION_MODEL = "gemini-1.5-flash-latest"

# --- Initialize Database ---
db_collection = None
try:
    client = chromadb.PersistentClient(path=VECTOR_STORE_PATH)
    db_collection = client.get_collection(name=COLLECTION_NAME)
    print("Successfully connected to the persistent vector database.")
except Exception as e:
    print(f"FATAL: Error connecting to vector database during startup.")
    traceback.print_exc()

# --- Configure Gemini API ---
api_key = os.environ.get('GEMINI_API_KEY')
if api_key:
    genai.configure(api_key=api_key)
else:
    print("FATAL: GEMINI_API_KEY not found in .env file.")

def get_gemini_rag_response(query: str) -> dict:
    if db_collection is None: return {"error": "Vector database is not available."}
    if not api_key: return {"error": "Gemini API key is not configured."}

    try:
        print("Step 1: Embedding user query with Gemini...")
        query_embedding = genai.embed_content(model=EMBEDDING_MODEL, content=query, task_type="retrieval_query")['embedding']
        print("Step 1a: Query embedded successfully.")

        print("Step 2: Retrieving relevant sections from Vector DB...")
        retrieved_results = db_collection.query(query_embeddings=[query_embedding], n_results=3)
        context = "\n\n".join(retrieved_results['documents'][0])
        print("Step 2a: Context retrieved successfully.")
    except Exception as e:
        print(f"ERROR during retrieval: {e}"); traceback.print_exc()
        return {"error": "An error occurred during the retrieval process."}

    try:
        print("\nStep 3: Generating response with Gemini...")
        model = genai.GenerativeModel(GENERATION_MODEL)
        prompt = f"You are an expert legal assistant. Based ONLY on the context below, analyze the user's query and list the potential legal sections that apply. Explain why each section is relevant.\n\nCONTEXT:\n{context}\n\nUSER QUERY:\n{query}\n\nANALYSIS:"
        response = model.generate_content(prompt)
        print("Step 3a: Received response from Gemini.")
        return {"analysis": response.text}
    except Exception as e:
        print(f"ERROR during generation: {e}"); traceback.print_exc()
        return {"error": "An error occurred during the generation process."}

def generate_fir_text(fir_data: dict) -> dict:
    """Uses Gemini to draft a formal FIR narrative from structured data."""
    if not api_key: return {"error": "Gemini API key is not configured."}

    try:
        print("Generating FIR text with Gemini...")
        model = genai.GenerativeModel(GENERATION_MODEL)
        
        # Create a detailed prompt from the structured data
        prompt = f"""
        You are a police officer in India writing a First Information Report (FIR).
        Your task is to take the structured information below and write a formal, clear, and concise FIR document.
        Combine the 'Complaint Details' with the other data points to create a coherent narrative.
        The final output should be the complete, formatted FIR text.

        --- STRUCTURED DATA ---
        - Police Station: {fir_data.get('incident', {}).get('ps', '(Not specified)')}
        - District: {fir_data.get('incident', {}).get('dist', '(Not specified)')}
        - Complainant Name: {fir_data.get('complainant', {}).get('name', '')}
        - Complainant Guardian: {fir_data.get('complainant', {}).get('guardian', '')}
        - Complainant Address: {fir_data.get('complainant', {}).get('address', '')}
        - Date of Occurrence: {fir_data.get('incident', {}).get('date', '')}
        - Time of Occurrence: {fir_data.get('incident', {}).get('time', '')}
        - Place of Occurrence: {fir_data.get('incident', {}).get('place', '')}
        - Initial AI Analysis of Offenses: {fir_data.get('aiAnalysis', '')}
        - Accused Details: {fir_data.get('accused', {}).get('details', 'Unknown')}
        - Witness Details: {fir_data.get('accused', {}).get('witnesses', 'None')}
        - Complaint Details (Narrative): {fir_data.get('crimeDescription', '')}
        ---

        Generate the complete FIR document based on this data.
        """
        
        response = model.generate_content(prompt)
        print("FIR text generated successfully.")
        return {"fir_text": response.text}
        
    except Exception as e:
        print(f"ERROR during FIR generation: {e}"); traceback.print_exc()
        return {"error": "An error occurred during the FIR generation process."}

