from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from app.config import get_settings
from app.services.llm_client import (
    AnthropicAuthError,
    GroqAuthError,
    LlmAuthError,
    LlmProvider,
    get_llm_client,
    normalize_llm_provider,
)
from app.models.api_schemas import ErrorResponse, UploadResponse
from app.models.socratic import ChunkNode, SessionData
from app.services.agentic_chunker import (
    CHUNK_TEST_MODE_MAX,
    ChunkLimitExceededError,
    agentic_chunk,
    estimate_source_chars_for_chunks,
)
from app.services.docling_parser import DoclingParseError, parse_pdf
from app.services.heading_generator import build_chunk_nodes, generate_headings
from app.services.hierarchy_builder import HierarchyValidationError, build_hierarchy
from app.session_store import create_session

router = APIRouter(prefix="/api", tags=["upload"])


def _require_provider_key(provider: LlmProvider) -> None:
    settings = get_settings()
    if provider == "groq" and not settings.groq_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "GROQ_API_KEY is not configured. "
                "Copy backend/.env.example to backend/.env and add your key, then restart the server."
            ),
        )
    if provider == "anthropic" and not settings.anthropic_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "ANTHROPIC_API_KEY is not configured. "
                "Copy backend/.env.example to backend/.env and add your key, then restart the server."
            ),
        )


@router.post(
    "/upload",
    response_model=UploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload PDF and create learning session",
    description=(
        "Accepts a PDF, parses with Docling, agentically chunks text "
        "(max 1000 chars), generates headings and semantic hierarchy."
    ),
    responses={
        422: {"model": ErrorResponse, "description": "Parse or chunking failure"},
        503: {"model": ErrorResponse, "description": "Missing API key or LLM unavailable"},
    },
)
async def upload_document(
    file: UploadFile = File(..., description="PDF document to ingest"),
    llm_provider: str = Form(
        "groq",
        description="LLM backend: groq or anthropic.",
    ),
) -> UploadResponse:
    settings = get_settings()
    try:
        provider = normalize_llm_provider(llm_provider)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    _require_provider_key(provider)

    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Only PDF files are supported.",
        )

    pdf_bytes = await file.read()
    if not pdf_bytes:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Uploaded file is empty.",
        )

    try:
        text = parse_pdf(pdf_bytes)
    except DoclingParseError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    if not text.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No extractable text found in PDF.",
        )

    try:
        client = get_llm_client(provider)
        char_budget = estimate_source_chars_for_chunks(
            CHUNK_TEST_MODE_MAX, settings.chunk_max_chars
        )
        text = text[:char_budget].strip()
        if not text:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="No extractable text within POC chunk budget.",
            )
        chunks = agentic_chunk(text, client=client, max_chunks=CHUNK_TEST_MODE_MAX)
        headings = generate_headings(chunks, client=client)
        raw_nodes = build_chunk_nodes(chunks, headings)
        edges, roots = build_hierarchy(raw_nodes, client=client)
    except ChunkLimitExceededError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except HierarchyValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except (GroqAuthError, AnthropicAuthError, LlmAuthError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    nodes = {nid: ChunkNode.model_validate(data) for nid, data in raw_nodes.items()}
    session: SessionData = create_session(nodes, edges, roots, llm_provider=provider)

    return UploadResponse(
        session_id=session.session_id,
        status="ready",
        node_count=len(nodes),
    )
