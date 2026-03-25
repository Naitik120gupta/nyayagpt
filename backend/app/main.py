import uvicorn
import os
import sys
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(CURRENT_DIR)
PROJECT_ROOT = os.path.dirname(BACKEND_DIR)

for import_path in (PROJECT_ROOT, BACKEND_DIR):
    if import_path not in sys.path:
        sys.path.insert(0, import_path)

try:
    from backend.app.api import endpoints
    from backend.app.core.config import settings
except ModuleNotFoundError:
    from app.api import endpoints
    from app.core.config import settings
import logging

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

app = FastAPI(title=settings.PROJECT_NAME)

# CORS
# For deployment, allow all origins by default (credentials must be False for wildcard)
# Or configure specific domains if needed
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(endpoints.router)

if __name__ == "__main__":
    uvicorn.run("backend.app.main:app", host="0.0.0.0", port=int(os.environ.get("PORT", 8000)), reload=True)
