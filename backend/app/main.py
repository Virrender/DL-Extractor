"""
Main FastAPI Application for Document Intelligence / IDP System.

Single unified endpoint: POST /api/v1/extract
Accepts front (required) + back (optional) images of an Aadhaar card or
Driving Licence, auto-detects the document type, and returns structured
extracted fields + a passport-style photo.
"""

import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes.document import router as document_router
from app.services.ocr_engine import PaddleOCREngine

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Pre-warming PaddleOCR deep learning models in RAM...")
    try:
        PaddleOCREngine()
        logger.info("PaddleOCR models successfully warmed up and ready in RAM.")
    except Exception as e:
        logger.warning(f"PaddleOCR model warm-up note: {e}")
    yield

app = FastAPI(
    title="Document Intelligence IDP",
    description="Intelligent Document Processing API for Identity Documents",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(document_router)


@app.get("/health", tags=["health"])
def health_check():
    """Simple health check endpoint."""
    return {"status": "healthy"}
