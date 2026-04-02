from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Dict, Any, Optional
import json
try:
    from backend.app.services.gemini_service import GeminiService
    from backend.app.services.rag_service import RAGService
except ModuleNotFoundError:
    from app.services.gemini_service import GeminiService
    from app.services.rag_service import RAGService
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


def _extract_json_payload(raw_text: str) -> Dict[str, Any]:
    text = (raw_text or "").strip()

    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].strip()

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("Model response does not contain a valid JSON object")

    payload = json.loads(text[start:end + 1])
    if not isinstance(payload, dict):
        raise ValueError("Parsed JSON payload is not an object")
    return payload


def _toolkit_fallback() -> Dict[str, Any]:
    return {
        "legal_analysis": {
            "sections": [],
            "explanation": "Unable to produce legal analysis at the moment.",
            "punishment": "Not available"
        },
        "route_recommendation": {
            "action_type": "Physical Station Visit",
            "instructions": "Carry identity proof, incident evidence, and any witness details to the nearest police station or legal aid center."
        },
        "complaint_summary": {
            "title": "Your Complaint Summary (Tehrir)",
            "disclaimer": "This is a summary to help you file, NOT an official police document.",
            "draft_text": "Please retry with clearer incident details (who, what, when, where, how) to generate a complaint summary."
        },
        "rights_reminder": {
            "title": "Know Your Rights",
            "text": "Under BNSS Section 173, police cannot refuse FIR registration for cognizable offences. If refused, approach the SP or magistrate under BNSS Section 175."
        }
    }

def get_gemini_service():
    return GeminiService()

def get_rag_service():
    return RAGService()

class QueryRequest(BaseModel):
    query: str
    complainant_name: Optional[str] = None
    accused_details: Optional[str] = None
    incident_address: Optional[str] = None
    incident_time: Optional[str] = None
    incident_date: Optional[str] = None

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

        logger.info("Step 3: Generating structured toolkit response...")
        analysis_prompt = f"""
You are NyayaGPT, a citizen legal empowerment assistant for Indian criminal law.

Analyze the incident using ONLY the provided legal context. Do not invent laws or facts.
Output STRICT JSON only. Do NOT use markdown, backticks, or extra keys.

Required JSON schema:
{{
    "legal_analysis": {{
        "sections": ["e.g., BNS Section 303 (Theft)", "BNS Section 331 (House Trespass)"],
        "explanation": "Plain language explanation of what these sections mean.",
        "punishment": "Maximum punishment details."
    }},
    "route_recommendation": {{
        "action_type": "Online e-FIR OR Physical Station Visit",
        "instructions": "If online, instruct use of state CCTNS portal; if physical, list documents/evidence to carry."
    }},
    "complaint_summary": {{
        "title": "Your Complaint Summary (Tehrir)",
        "disclaimer": "This is a summary to help you file, NOT an official police document.",
        "draft_text": "A highly professional first-person chronological narrative (Who, What, When, Where, How)."
    }},
    "rights_reminder": {{
        "title": "Know Your Rights",
        "text": "Under BNSS Section 173, police cannot refuse to register an FIR for a cognizable offense. If they refuse, you can approach the Superintendent of Police or file a complaint before a magistrate under BNSS Section 175."
    }}
}}

CONTEXT:
{retrieved_context}

USER INCIDENT:
{request.query}

INCIDENT DETAILS (use when available and relevant in complaint_summary.draft_text):
- Complainant Name: {request.complainant_name or 'Not provided'}
- Accused Details: {request.accused_details or 'Not provided'}
- Incident Address: {request.incident_address or 'Not provided'}
- Incident Time: {request.incident_time or 'Not provided'}
- Incident Date: {request.incident_date or 'Not provided'}
"""

        analysis_text = gemini_service.generate_content(analysis_prompt)
        logger.info("Step 3a: Received response from Gemini.")

        try:
            analysis_payload = _extract_json_payload(analysis_text)
        except Exception as parse_error:
            logger.warning(f"Failed to parse model JSON output: {parse_error}")
            analysis_payload = _toolkit_fallback()

        return {"analysis": analysis_payload}

    except Exception as e:
        logger.error(f"Error processing /analyze request: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/generate-fir")
async def generate_fir(
    request: FirDataRequest,
    gemini_service: GeminiService = Depends(get_gemini_service)
):
    logger.warning("/generate-fir is deprecated in Citizen Legal Empowerment Toolkit mode.")
    raise HTTPException(
        status_code=410,
        detail="FIR document generation has been deprecated. Use /analyze for toolkit output."
    )
