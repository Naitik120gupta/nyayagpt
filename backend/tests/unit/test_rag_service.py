"""
Unit tests for backend.app.services.rag_service
"""
from unittest.mock import MagicMock, patch

import pytest

from app.services.rag_service import RAGService


def _make_service_with_retriever(retriever_mock):
    svc = RAGService.__new__(RAGService)
    svc.retriever = retriever_mock
    return svc


class TestRAGServiceQuerySimilarDocuments:
    def test_returns_documents_on_success(self):
        mock_retriever = MagicMock()
        mock_retriever.retrieve.return_value = {
            "results": [
                {"document": "BNS Section 303: Theft.", "score": 0.90},
                {"document": "BNS Section 304: Snatching.", "score": 0.85},
            ]
        }
        svc = _make_service_with_retriever(mock_retriever)
        docs = svc.query_similar_documents("someone stole my phone")
        assert docs == ["BNS Section 303: Theft.", "BNS Section 304: Snatching."]

    def test_returns_empty_list_when_retriever_is_none(self):
        svc = RAGService.__new__(RAGService)
        svc.retriever = None
        docs = svc.query_similar_documents("query")
        assert docs == []

    def test_propagates_valueerror(self):
        mock_retriever = MagicMock()
        mock_retriever.retrieve.side_effect = ValueError(
            "No sufficiently relevant BNS sections found"
        )
        svc = _make_service_with_retriever(mock_retriever)
        with pytest.raises(ValueError, match="relevant BNS sections"):
            svc.query_similar_documents("vague query")

    def test_swallows_generic_exceptions(self):
        mock_retriever = MagicMock()
        mock_retriever.retrieve.side_effect = RuntimeError("chromadb connection error")
        svc = _make_service_with_retriever(mock_retriever)
        docs = svc.query_similar_documents("query")
        assert docs == []

    def test_swallows_attribute_error(self):
        mock_retriever = MagicMock()
        mock_retriever.retrieve.side_effect = AttributeError("collection not found")
        svc = _make_service_with_retriever(mock_retriever)
        docs = svc.query_similar_documents("query")
        assert docs == []

    def test_passes_n_results_to_retrieve(self):
        mock_retriever = MagicMock()
        mock_retriever.retrieve.return_value = {"results": []}
        svc = _make_service_with_retriever(mock_retriever)
        # Will raise ValueError because results is empty after filtering
        # — but we only care that k was passed correctly
        try:
            svc.query_similar_documents("query", n_results=7)
        except (ValueError, Exception):
            pass
        mock_retriever.retrieve.assert_called_with("query", k=7)
