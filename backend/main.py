import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any
from rag_handler import get_gemini_rag_response, generate_fir_text
import os

app = FastAPI(title="Nyay Sahayak API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
origins = [
    "https://nyayagpt.vercel.app/",
    "http://localhost",
    "http://localhost:8081",
    "http://127.0.0.1:5500",
]
class QueryRequest(BaseModel):
    query: str

class FirDataRequest(BaseModel):
    firData: Dict[str, Any]

@app.post("/analyze")
async def analyze_crime(query_request: QueryRequest):
    print(f"Received API call to /analyze with query: {query_request.query}")
    analysis_response = get_gemini_rag_response(query=query_request.query)
    return analysis_response

@app.post("/generate-fir")
async def generate_fir(fir_data_request: Dict[str, Any]):
    print(f"Received API call to /generate-fir")
    fir_response = generate_fir_text(fir_data=fir_data_request)
    return fir_response

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
