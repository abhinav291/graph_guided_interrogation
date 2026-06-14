from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field

from app.models.socratic import SocraticAssessment


class HealthResponse(BaseModel):
    status: str = "ok"


class ErrorResponse(BaseModel):
    detail: Union[str, Dict[str, Any]]


class UploadResponse(BaseModel):
    session_id: str
    status: str
    node_count: int


class TreeNode(BaseModel):
    id: str
    heading: str
    is_completed: bool = False


class TreeEdgeSchema(BaseModel):
    source: str
    target: str


class TreeResponse(BaseModel):
    nodes: List[TreeNode]
    edges: List[TreeEdgeSchema]


class NodeDetailResponse(BaseModel):
    node_id: str
    heading: str
    is_completed: bool
    assessment_ready: bool
    full_chunk_text: Optional[str] = None


class GenerateAssessmentResponse(BaseModel):
    node_id: str
    heading: str
    full_chunk_text: str
    socratic_assessment: SocraticAssessment


class CompleteNodeRequest(BaseModel):
    selected_path: List[str] = Field(..., min_length=1)
    was_correct: bool


class CompleteNodeResponse(BaseModel):
    node_id: str
    is_completed: bool


class FallbackLogRequest(BaseModel):
    layer: int = Field(..., ge=0, le=3)
    selected_path_prefix: List[str] = Field(..., min_length=1)
    custom_text: str = Field(..., min_length=1)


class FallbackLogResponse(BaseModel):
    logged: bool
    entry_id: str
