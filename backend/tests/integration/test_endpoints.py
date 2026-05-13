"""
Integration tests for the FastAPI endpoints.

GeminiService and RAGService are mocked — no model or API key required.
"""
import json
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import app  # must be imported first — it adds PROJECT_ROOT to sys.path
# After app.main runs, backend.app.api.endpoints is registered in sys.modules.
# We must use that same object as the key in dependency_overrides.
import sys as _sys
_ep = _sys.modules.get("backend.app.api.endpoints") or _sys.modules["app.api.endpoints"]
get_gemini_service = _ep.get_gemini_service
get_rag_service = _ep.get_rag_service

VALID_ANALYSIS_RESPONSE = {
    "validation_layer": {
        "is_valid": True,
        "warnings": [],
        "offense_category": "Cognizable",
    },
    "legal_analysis": {
        "sections": ["BNS Section 303(2) (Theft)"],
        "explanation": "Theft of movable property without consent.",
        "nature": "Cognizable and Non-Bailable",
        "punishment": "Imprisonment up to 3 years.",
    },
    "route_recommendation": {
        "action_type": "Physical Station Visit",
        "portal_link": None,
        "instructions": "Visit nearest police station with evidence.",
    },
    "smart_pre_fill": {
        "title": "FIR Preparation Summary",
        "draft_text": "On 01-01-2025, my phone was stolen.",
    },
    "rights_reminder": {
        "text": "Under BNSS Section 173, police must register the FIR.",
    },
}


@pytest.fixture()
def client():
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture()
def mock_services():
    """Override FastAPI dependencies so no real model or API key is needed."""
    mock_gemini = MagicMock()
    mock_gemini.generate_content.return_value = json.dumps(VALID_ANALYSIS_RESPONSE)

    mock_rag = MagicMock()
    mock_rag.query_similar_documents.return_value = [
        "BNS Section 303: Theft — whoever takes movable property without consent.",
    ]

    app.dependency_overrides[get_gemini_service] = lambda: mock_gemini
    app.dependency_overrides[get_rag_service] = lambda: mock_rag
    yield mock_gemini, mock_rag
    app.dependency_overrides.clear()


# ─── /analyze ─────────────────────────────────────────────────────────────────

class TestAnalyzeEndpoint:
    def test_returns_200_with_valid_query(self, client, mock_services):
        resp = client.post("/analyze", json={"query": "Someone stole my phone"})
        assert resp.status_code == 200

    def test_response_contains_analysis_key(self, client, mock_services):
        resp = client.post("/analyze", json={"query": "Someone stole my phone"})
        data = resp.json()
        assert "analysis" in data

    def test_analysis_contains_all_five_keys(self, client, mock_services):
        resp = client.post("/analyze", json={"query": "Someone stole my phone"})
        analysis = resp.json()["analysis"]
        required_keys = {
            "validation_layer",
            "legal_analysis",
            "route_recommendation",
            "smart_pre_fill",
            "rights_reminder",
        }
        assert required_keys == set(analysis.keys())

    def test_validation_layer_structure(self, client, mock_services):
        resp = client.post("/analyze", json={"query": "I was robbed"})
        vl = resp.json()["analysis"]["validation_layer"]
        assert "is_valid" in vl
        assert "warnings" in vl
        assert "offense_category" in vl

    def test_legal_analysis_structure(self, client, mock_services):
        resp = client.post("/analyze", json={"query": "I was robbed"})
        la = resp.json()["analysis"]["legal_analysis"]
        assert "sections" in la
        assert "explanation" in la
        assert "nature" in la
        assert "punishment" in la

    def test_optional_fields_accepted(self, client, mock_services):
        payload = {
            "query": "My husband beats me for dowry",
            "complainant_name": "Priya Sharma",
            "accused_details": "Husband Rajesh",
            "incident_date": "2025-01-01",
            "incident_time": "22:00",
            "incident_address": "Delhi",
        }
        resp = client.post("/analyze", json=payload)
        assert resp.status_code == 200

    def test_fallback_on_invalid_gemini_json(self, client):
        mock_gemini = MagicMock()
        mock_gemini.generate_content.return_value = "not valid json at all"
        mock_rag = MagicMock()
        mock_rag.query_similar_documents.return_value = ["Section 303 text"]

        app.dependency_overrides[get_gemini_service] = lambda: mock_gemini
        app.dependency_overrides[get_rag_service] = lambda: mock_rag
        try:
            resp = client.post("/analyze", json={"query": "theft"})
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        assert "validation_layer" in resp.json()["analysis"]

    def test_422_when_no_relevant_sections_found(self, client):
        mock_gemini = MagicMock()
        mock_rag = MagicMock()
        mock_rag.query_similar_documents.side_effect = ValueError(
            "No sufficiently relevant BNS sections found for this query. "
            "Please describe the incident in more detail."
        )
        app.dependency_overrides[get_gemini_service] = lambda: mock_gemini
        app.dependency_overrides[get_rag_service] = lambda: mock_rag
        try:
            resp = client.post("/analyze", json={"query": "abc"})
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 422
        assert "more detail" in resp.json()["detail"]

    def test_500_when_gemini_raises(self, client):
        mock_gemini = MagicMock()
        mock_gemini.generate_content.side_effect = RuntimeError("API down")
        mock_rag = MagicMock()
        mock_rag.query_similar_documents.return_value = ["some section"]
        app.dependency_overrides[get_gemini_service] = lambda: mock_gemini
        app.dependency_overrides[get_rag_service] = lambda: mock_rag
        try:
            resp = client.post("/analyze", json={"query": "theft"})
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 500

    def test_empty_query_accepted_but_may_fail_retrieval(self, client):
        mock_rag = MagicMock()
        mock_rag.query_similar_documents.side_effect = ValueError(
            "No sufficiently relevant BNS sections found"
        )
        mock_gemini = MagicMock()
        app.dependency_overrides[get_gemini_service] = lambda: mock_gemini
        app.dependency_overrides[get_rag_service] = lambda: mock_rag
        try:
            resp = client.post("/analyze", json={"query": ""})
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code in (200, 422, 500)


# ─── /generate-fir (deprecated) ───────────────────────────────────────────────

class TestGenerateFirEndpoint:
    def test_returns_410_gone(self, client):
        resp = client.post("/generate-fir", json={"firData": {}})
        assert resp.status_code == 410

    def test_410_detail_mentions_analyze(self, client):
        resp = client.post("/generate-fir", json={"firData": {}})
        assert "analyze" in resp.json()["detail"].lower()
