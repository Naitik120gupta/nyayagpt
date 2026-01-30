from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Dict, Any
from backend.app.services.gemini_service import GeminiService
from backend.app.services.rag_service import RAGService
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

def get_gemini_service():
    return GeminiService()

def get_rag_service():
    return RAGService()

class QueryRequest(BaseModel):
    query: str

class FirDataRequest(BaseModel):
    firData: Dict[str, Any]

@router.post("/analyze")
async def analyze_crime(
    request: QueryRequest,
    gemini_service: GeminiService = Depends(get_gemini_service),
    rag_service: RAGService = Depends(get_rag_service)
):
    logger.info(f"Received API call to /analyze with query: {request.query}")

    try:
        logger.info("Step 1: Embedding user query...")
        embedded_query = gemini_service.get_embedding(request.query)

        logger.info("Step 2: Retrieving relevant sections...")
        documents = rag_service.query_similar_documents(embedded_query)

        if not documents:
            logger.warning("No relevant documents found.")
            retrieved_context = "No specific legal sections found in the database."
        else:
            retrieved_context = "\n\n".join(documents)
            logger.info("Step 2a: Context retrieved successfully.")

        logger.info("Step 3: Generating response...")
        analysis_prompt = f"You are an expert legal assistant. Based ONLY on the context below, analyze the user's query and list the potential legal sections that apply. Explain why each section is relevant.\n\nCONTEXT:\n{retrieved_context}\n\nUSER QUERY:\n{request.query}\n\nANALYSIS:"

        analysis_text = gemini_service.generate_content(analysis_prompt)
        logger.info("Step 3a: Received response from Gemini.")

        return {"analysis": analysis_text}

    except Exception as e:
        logger.error(f"Error processing /analyze request: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/generate-fir")
async def generate_fir(
    request: FirDataRequest,
    gemini_service: GeminiService = Depends(get_gemini_service)
):
    logger.info("Received API call to /generate-fir")

    try:
        fir_data = request.firData

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

        fir_text = gemini_service.generate_content(fir_generation_prompt)
        logger.info("FIR text generated successfully.")

        return {"fir_text": fir_text}

    except Exception as e:
        logger.error(f"Error processing /generate-fir request: {e}")
        raise HTTPException(status_code=500, detail=str(e))
