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
        "validation_layer": {
            "is_valid": False,
            "warnings": [
                "Unable to complete AI validation. Please verify incident date, time, complainant, accused details, and chronology manually before filing."
            ],
            "offense_category": "Cognizable"
        },
        "legal_analysis": {
            "sections": [],
            "explanation": "Unable to produce legal analysis at the moment.",
            "nature": "Not available",
            "punishment": "Not available"
        },
        "route_recommendation": {
            "action_type": "Physical Station Visit",
            "portal_link": None,
            "instructions": "Carry identity proof, incident evidence, and any witness details to the nearest police station or legal aid center."
        },
        "smart_pre_fill": {
            "title": "FIR Preparation Summary",
            "draft_text": "Please retry with clearer incident details (who, what, when, where, how) to generate Smart FIR pre-fill data for CCTNS IIF-1 preparation."
        },
        "rights_reminder": {
            "text": "Under BNSS Section 173, police must register information relating to cognizable offences. If refused, escalate to the Superintendent of Police or approach the Magistrate under BNSS remedies."
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
    complainant_address: Optional[str] = None
    police_station: Optional[str] = None
    witness_details: Optional[str] = None
    additional_facts: Optional[str] = None

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
You are NyayaGPT, an AI legal assistant for Indian criminal law focused on citizen FIR preparation.

STRICT LEGAL SCOPE:
- Use ONLY Bharatiya Nyaya Sanhita, 2023 (BNS) and Bharatiya Nagarik Suraksha Sanhita, 2023 (BNSS).
- COMPLETELY IGNORE IPC and CrPC references even if mentioned by user.
- Do not invent sections, procedures, punishments, links, or facts.

OUTPUT RULES:
- Return STRICT JSON only.
- No markdown, no backticks, no prose outside JSON.
- Top-level object MUST contain exactly these 5 keys and no others:
    1) validation_layer
    2) legal_analysis
    3) route_recommendation
    4) smart_pre_fill
    5) rights_reminder

Required JSON schema:
{{
    "validation_layer": {{
        "is_valid": true,
        "warnings": ["List logical consistency warnings if any, else empty array"],
        "offense_category": "Cognizable or Non-Cognizable"
    }},
    "legal_analysis": {{
        "sections": ["BNS Section 303(2) (Theft)"],
        "explanation": "Plain-language explanation based on BNS/BNSS context.",
        "nature": "Cognizable/Non-Cognizable and Bailable/Non-Bailable, if inferable from given context.",
        "punishment": "Maximum punishment details from available context."
    }},
    "route_recommendation": {{
        "action_type": "Online e-FIR Portal OR Physical Station Visit",
        "portal_link": "State e-FIR portal URL if confidently inferable, otherwise null",
        "instructions": "Actionable filing guidance for citizen."
    }},
    "smart_pre_fill": {{
        "title": "FIR Preparation Summary",
        "draft_text": "Chronological first-person narrative suitable as pre-fill data for CCTNS IIF-1."
    }},
    "rights_reminder": {{
        "text": "Rights reminder referencing BNSS Section 173."
    }}
}}

VALIDATION REQUIREMENTS:
- In validation_layer.warnings, flag logical issues such as missing date/time/place, contradictory sequence, complainant and accused appearing identical without explanation, or unclear accused identity.
- Set validation_layer.is_valid to false if major critical facts are missing or contradictory; otherwise true.

CONTEXT:
{retrieved_context}

USER INCIDENT:
{request.query}

INCIDENT DETAILS (use in smart_pre_fill.draft_text and validation checks):
- Complainant Name: {request.complainant_name or 'Not provided'}
- Complainant Address: {request.complainant_address or 'Not provided'}
- Accused Details: {request.accused_details or 'Not provided'}
- Incident Address: {request.incident_address or 'Not provided'}
- Incident Time: {request.incident_time or 'Not provided'}
- Incident Date: {request.incident_date or 'Not provided'}
- Police Station (if known): {request.police_station or 'Not provided'}
- Witness Details: {request.witness_details or 'Not provided'}
- Additional Facts: {request.additional_facts or 'Not provided'}
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
