from __future__ import annotations

import json

from app.services.llm_client import LlmClient, get_llm_client

HEADING_SYSTEM = """You generate concise semantic headings for document chunks.
Return ONLY valid JSON: { "headings": ["heading1", "heading2", ...] }
Each heading must be at most 8 words and capture the core theme of its chunk.
The headings array length MUST equal the number of chunks provided.
"""


def generate_headings(
    chunks: list[str],
    client: LlmClient | None = None,
) -> list[str]:
    client = client or get_llm_client()
    payload = [{"index": i + 1, "preview": c[:300]} for i, c in enumerate(chunks)]
    user = json.dumps({"chunks": payload}, ensure_ascii=False)
    result = client.complete_json(HEADING_SYSTEM, user, max_tokens=2048)
    headings = result.get("headings", [])

    if len(headings) != len(chunks):
        headings = [
            h if i < len(headings) else f"Section {i + 1}"
            for i, h in enumerate(headings[: len(chunks)])
        ]
        while len(headings) < len(chunks):
            headings.append(f"Section {len(headings) + 1}")

    return [str(h).strip() for h in headings]


def build_chunk_nodes(chunks: list[str], headings: list[str]) -> dict[str, dict]:
    nodes: dict[str, dict] = {}
    for i, (chunk, heading) in enumerate(zip(chunks, headings)):
        node_id = f"node_chunk_{i + 1:02d}"
        nodes[node_id] = {
            "node_id": node_id,
            "heading": heading,
            "full_chunk_text": chunk,
            "is_completed": False,
            "custom_fallback_logs": [],
            "socratic_assessment": None,
        }
    return nodes
