from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Dict, List, Optional

from app.models.socratic import ChunkNode, SessionData, TreeEdge

SESSIONS: Dict[str, SessionData] = {}
_DEFAULT_SESSIONS_DIR = Path(__file__).resolve().parents[1] / "data" / "sessions"
SESSIONS_DIR = Path(os.environ.get("SESSIONS_DIR", str(_DEFAULT_SESSIONS_DIR)))


def _ensure_sessions_dir() -> None:
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)


def _session_path(session_id: str) -> Path:
    return SESSIONS_DIR / f"{session_id}.json"


def _save_session(session: SessionData) -> None:
    _ensure_sessions_dir()
    _session_path(session.session_id).write_text(
        session.model_dump_json(indent=2),
        encoding="utf-8",
    )


def _load_sessions() -> None:
    _ensure_sessions_dir()
    for path in SESSIONS_DIR.glob("*.json"):
        try:
            session = SessionData.model_validate_json(path.read_text(encoding="utf-8"))
            SESSIONS[session.session_id] = session
        except Exception:
            continue


def create_session(
    nodes: Dict[str, ChunkNode],
    tree_edges: List[TreeEdge],
    root_node_ids: List[str],
    *,
    llm_provider: str = "groq",
) -> SessionData:
    session_id = str(uuid.uuid4())
    session = SessionData(
        session_id=session_id,
        nodes=nodes,
        tree_edges=tree_edges,
        root_node_ids=root_node_ids,
        llm_provider=llm_provider,
    )
    SESSIONS[session_id] = session
    _save_session(session)
    return session


def get_session(session_id: str) -> Optional[SessionData]:
    return SESSIONS.get(session_id)


def get_node(session_id: str, node_id: str) -> Optional[ChunkNode]:
    session = get_session(session_id)
    if session is None:
        return None
    return session.nodes.get(node_id)


def update_node(session_id: str, node_id: str, node: ChunkNode) -> None:
    session = get_session(session_id)
    if session is None:
        raise KeyError(f"Session {session_id} not found")
    session.nodes[node_id] = node
    _save_session(session)


_load_sessions()
