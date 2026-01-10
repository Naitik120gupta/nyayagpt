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
ipc_collection = None
try:
    chroma_client = chromadb.PersistentClient(path=VECTOR_STORE_PATH)
    ipc_collection = chroma_client.get_collection(name=COLLECTION_NAME)
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
    if ipc_collection is None: return {"error": "Vector database is not available."}
    if not api_key: return {"error": "Gemini API key is not configured."}

    try:
        print("Step 1: Embedding user query with Gemini...")
        embedded_query = genai.embed_content(model=EMBEDDING_MODEL, content=query, task_type="retrieval_query")['embedding']
        print("Step 1a: Query embedded successfully.")

        print("Step 2: Retrieving relevant sections from Vector DB...")
        search_results = ipc_collection.query(query_embeddings=[embedded_query], n_results=3)
        retrieved_legal_context = "\n\n".join(search_results['documents'][0])
        print("Step 2a: Context retrieved successfully.")
    except Exception as e:
        print(f"ERROR during retrieval: {e}"); traceback.print_exc()
        return {"error": "An error occurred during the retrieval process."}

    try:
        print("\nStep 3: Generating response with Gemini...")
        gemini_model = genai.GenerativeModel(GENERATION_MODEL)
        analysis_prompt = f"You are an expert legal assistant. Based ONLY on the context below, analyze the user's query and list the potential legal sections that apply. Explain why each section is relevant.\n\nCONTEXT:\n{retrieved_legal_context}\n\nUSER QUERY:\n{query}\n\nANALYSIS:"
        gemini_response = gemini_model.generate_content(analysis_prompt)
        print("Step 3a: Received response from Gemini.")
        return {"analysis": gemini_response.text}
    except Exception as e:
        print(f"ERROR during generation: {e}"); traceback.print_exc()
        return {"error": "An error occurred during the generation process."}

def generate_fir_text(fir_data: dict) -> dict:
    """Uses Gemini to draft a formal FIR narrative from structured data."""
    if not api_key: return {"error": "Gemini API key is not configured."}

    try:
        print("Generating FIR text with Gemini...")
        gemini_model = genai.GenerativeModel(GENERATION_MODEL)
        
        # Create a detailed prompt from the structured data
        fir_generation_prompt = f"""
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
        
        fir_response = gemini_model.generate_content(fir_generation_prompt)
        print("FIR text generated successfully.")
        return {"fir_text": fir_response.text}
        
    except Exception as e:
        print(f"ERROR during FIR generation: {e}"); traceback.print_exc()
        return {"error": "An error occurred during the FIR generation process."}

