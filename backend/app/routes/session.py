from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status

from app.models.api_schemas import (
    CompleteNodeRequest,
    CompleteNodeResponse,
    ErrorResponse,
    FallbackLogRequest,
    FallbackLogResponse,
    GenerateAssessmentResponse,
    NodeDetailResponse,
    TreeEdgeSchema,
    TreeNode,
    TreeResponse,
)
from app.models.socratic import ChunkNode, FallbackLogEntry
from app.services.socratic_generator import SocraticGenerationError, ensure_assessment
from app.session_store import get_node, get_session, update_node

router = APIRouter(prefix="/api/session", tags=["session"])


def _require_session(session_id: str):
    session = get_session(session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found",
        )
    return session


def _require_node(session_id: str, node_id: str) -> ChunkNode:
    _require_session(session_id)
    node = get_node(session_id, node_id)
    if node is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Node {node_id} not found in session {session_id}",
        )
    return node


@router.get(
    "/{session_id}/tree",
    response_model=TreeResponse,
    summary="Get session tree graph",
    description="Returns node headings and edges for React Flow rendering.",
    responses={404: {"model": ErrorResponse}},
)
async def get_tree(session_id: str) -> TreeResponse:
    session = _require_session(session_id)
    nodes = [
        TreeNode(
            id=node.node_id,
            heading=node.heading,
            is_completed=node.is_completed,
        )
        for node in session.nodes.values()
    ]
    edges = [
        TreeEdgeSchema(source=e.parent_id, target=e.child_id)
        for e in session.tree_edges
    ]
    return TreeResponse(nodes=nodes, edges=edges)


@router.get(
    "/{session_id}/node/{node_id}",
    response_model=NodeDetailResponse,
    summary="Get node metadata",
    responses={404: {"model": ErrorResponse}},
)
async def get_node_detail(session_id: str, node_id: str) -> NodeDetailResponse:
    node = _require_node(session_id, node_id)
    assessment_ready = node.socratic_assessment is not None
    full_text = node.full_chunk_text if assessment_ready or node.is_completed else None
    return NodeDetailResponse(
        node_id=node.node_id,
        heading=node.heading,
        is_completed=node.is_completed,
        assessment_ready=assessment_ready,
        full_chunk_text=full_text,
    )


@router.post(
    "/{session_id}/node/{node_id}/generate",
    response_model=GenerateAssessmentResponse,
    summary="Generate or return cached Socratic assessment",
    responses={
        404: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
)
async def generate_assessment(
    session_id: str, node_id: str
) -> GenerateAssessmentResponse:
    session = _require_session(session_id)
    node = _require_node(session_id, node_id)
    try:
        assessment = ensure_assessment(node, llm_provider=session.llm_provider)
        update_node(session_id, node_id, node)
    except SocraticGenerationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    return GenerateAssessmentResponse(
        node_id=node.node_id,
        heading=node.heading,
        full_chunk_text=node.full_chunk_text,
        socratic_assessment=assessment,
    )


@router.patch(
    "/{session_id}/node/{node_id}/complete",
    response_model=CompleteNodeResponse,
    summary="Mark node assessment as completed",
    responses={404: {"model": ErrorResponse}},
)
async def complete_node(
    session_id: str,
    node_id: str,
    body: CompleteNodeRequest,
) -> CompleteNodeResponse:
    node = _require_node(session_id, node_id)
    node.is_completed = True
    node.selected_path = body.selected_path
    node.was_correct = body.was_correct
    update_node(session_id, node_id, node)
    return CompleteNodeResponse(node_id=node_id, is_completed=True)


@router.post(
    "/{session_id}/node/{node_id}/fallback-log",
    response_model=FallbackLogResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Log custom fallback reasoning",
    responses={404: {"model": ErrorResponse}},
)
async def log_fallback(
    session_id: str,
    node_id: str,
    body: FallbackLogRequest,
) -> FallbackLogResponse:
    node = _require_node(session_id, node_id)
    entry_id = f"fb_{uuid.uuid4().hex[:8]}"
    entry = FallbackLogEntry(
        entry_id=entry_id,
        layer=body.layer,
        selected_path_prefix=body.selected_path_prefix,
        custom_text=body.custom_text,
    )
    node.custom_fallback_logs.append(entry)
    update_node(session_id, node_id, node)
    return FallbackLogResponse(logged=True, entry_id=entry_id)
