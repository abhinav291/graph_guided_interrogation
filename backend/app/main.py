from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.models.api_schemas import HealthResponse
from app.routes import session, upload

app = FastAPI(
    title="Socratic Graph Learning API",
    description="PDF upload, agentic chunking, and session-bound Socratic assessment trees.",
    version="0.1.0",
    openapi_tags=[
        {"name": "health", "description": "Liveness checks"},
        {"name": "upload", "description": "PDF ingestion and session creation"},
        {"name": "session", "description": "Tree graph and node assessment endpoints"},
    ],
)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload.router)
app.include_router(session.router)


@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["health"],
    summary="Health check",
)
async def health() -> HealthResponse:
    return HealthResponse()
