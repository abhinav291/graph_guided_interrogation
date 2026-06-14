from __future__ import annotations

import re
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from app.services.llm_client import FALLBACK_LABEL, MCQ_KEYS, OPTION_MAX_WORDS

McqKey = Literal["A", "B", "C", "D"]


def _validate_word_limit(text: str, field_name: str) -> str:
    words = text.split()
    if len(words) > OPTION_MAX_WORDS:
        raise ValueError(
            f"{field_name} must be at most {OPTION_MAX_WORDS} words, got {len(words)}"
        )
    return text


class SocraticOption(BaseModel):
    id: str
    text: str

    @field_validator("text")
    @classmethod
    def validate_text_words(cls, v: str) -> str:
        return _validate_word_limit(v, "option text")


class Layer2Branch(BaseModel):
    layer_2_question: str
    layer_2_options: List[SocraticOption]

    @field_validator("layer_2_options")
    @classmethod
    def validate_options(cls, v: List[SocraticOption]) -> List[SocraticOption]:
        _validate_layer_options(v, "layer_2_options")
        return v


class McqBranch(BaseModel):
    layer_1_question: str
    layer_1_options: List[SocraticOption]
    layer_2_branches: Dict[str, Layer2Branch] = Field(default_factory=dict)
    layer_3_question: str
    layer_3_options: List[SocraticOption]

    @field_validator("layer_1_options")
    @classmethod
    def validate_l1_options(cls, v: List[SocraticOption]) -> List[SocraticOption]:
        _validate_layer_options(v, "layer_1_options")
        return v

    @field_validator("layer_3_options")
    @classmethod
    def validate_l3_options(cls, v: List[SocraticOption]) -> List[SocraticOption]:
        _validate_layer_options(v, "layer_3_options")
        return v

    @model_validator(mode="after")
    def validate_l2_branches(self) -> McqBranch:
        for opt in self.layer_1_options:
            if opt.id.startswith("fallback_"):
                continue
            if opt.id not in self.layer_2_branches:
                raise ValueError(f"Missing layer_2 branch for L1 option {opt.id}")
        return self


class SocraticAssessment(BaseModel):
    question_text: str
    options: Dict[str, str]
    correct_option: McqKey
    option_feedback: Dict[str, str] = Field(default_factory=dict)
    socratic_tree: Dict[str, McqBranch]
    reasoning_feedback: Dict[str, str] = Field(default_factory=dict)
    topper_path: List[str]
    topper_explanation: str

    @field_validator("options")
    @classmethod
    def validate_mcq_options(cls, v: Dict[str, str]) -> Dict[str, str]:
        if set(v.keys()) != set(MCQ_KEYS):
            raise ValueError("MCQ options must contain exactly A, B, C, D")
        for key, text in v.items():
            _validate_word_limit(text, f"MCQ option {key}")
        return v

    @model_validator(mode="after")
    def validate_tree(self) -> SocraticAssessment:
        if self.correct_option not in self.socratic_tree:
            raise ValueError("correct_option must exist in socratic_tree")
        if not self.topper_path:
            raise ValueError("topper_path must not be empty")
        if self.topper_path[0] != self.correct_option:
            raise ValueError("topper_path must start with correct_option")
        return self


def _validate_layer_options(options: List[SocraticOption], field: str) -> None:
    if len(options) != 4:
        raise ValueError(f"{field} must contain exactly 4 options")
    fallback_count = sum(1 for o in options if o.id.startswith("fallback_"))
    if fallback_count != 1:
        raise ValueError(f"{field} must contain exactly one fallback option")
    fallback = next(o for o in options if o.id.startswith("fallback_"))
    if fallback.text != FALLBACK_LABEL:
        raise ValueError(f"Fallback option text must be exactly: {FALLBACK_LABEL}")


class FallbackLogEntry(BaseModel):
    entry_id: str
    layer: int
    selected_path_prefix: List[str]
    custom_text: str


class ChunkNode(BaseModel):
    node_id: str
    heading: str
    full_chunk_text: str
    is_completed: bool = False
    selected_path: Optional[List[str]] = None
    was_correct: Optional[bool] = None
    custom_fallback_logs: List[FallbackLogEntry] = Field(default_factory=list)
    socratic_assessment: Optional[SocraticAssessment] = None


class TreeEdge(BaseModel):
    parent_id: str
    child_id: str


class SessionData(BaseModel):
    session_id: str
    nodes: Dict[str, ChunkNode]
    tree_edges: List[TreeEdge]
    root_node_ids: List[str]
    llm_provider: str = "groq"
