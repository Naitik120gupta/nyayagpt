"""
Shared fixtures and path setup for the NyayaGPT test suite.
"""
import os
import sys
import tempfile
import types

import pytest

# ── make backend importable without installing it ─────────────────────────────
_BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
# Only add BACKEND_DIR so that "from backend.app..." paths in main.py/endpoints.py
# fall back to the "from app..." branch — ensuring a single module identity for
# dependency_overrides to work correctly in tests.
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

# ── stub heavy deps so unit tests import without GPU/model ────────────────────

# chromadb
_chromadb = types.ModuleType("chromadb")
_chromadb.PersistentClient = MagicMock = __import__("unittest.mock", fromlist=["MagicMock"]).MagicMock
sys.modules.setdefault("chromadb", _chromadb)

# google.genai
_google = types.ModuleType("google")
_google_genai = types.ModuleType("google.genai")
_google.genai = _google_genai
sys.modules.setdefault("google", _google)
sys.modules.setdefault("google.genai", _google_genai)

# sentence_transformers — needs SentenceTransformer class + models submodule
from unittest.mock import MagicMock as _MagicMock

_st = types.ModuleType("sentence_transformers")
_st.SentenceTransformer = _MagicMock
sys.modules.setdefault("sentence_transformers", _st)

_st_models = types.ModuleType("sentence_transformers.models")
_st_models.Transformer = _MagicMock
_st_models.Pooling = _MagicMock
_st_models.Normalize = _MagicMock
_st.models = _st_models
sys.modules.setdefault("sentence_transformers.models", _st_models)

# numpy — use real numpy if available, otherwise stub
try:
    import numpy as np  # noqa: F401
except ImportError:
    _np = types.ModuleType("numpy")
    _np.float32 = float
    sys.modules.setdefault("numpy", _np)

# dotenv stub
_dotenv = types.ModuleType("dotenv")
_dotenv.load_dotenv = lambda: None
sys.modules.setdefault("dotenv", _dotenv)


# ── helpers ──────────────────────────────────────────────────────────────────
@pytest.fixture()
def tmp_db(tmp_path):
    """Return a path to a temporary SQLite file."""
    return str(tmp_path / "test.sqlite3")


@pytest.fixture()
def bns_csv_path():
    return os.path.join(_BACKEND_DIR, "data", "bns_augmented.csv")
