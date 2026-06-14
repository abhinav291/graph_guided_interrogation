from __future__ import annotations

import json

from app.models.socratic import TreeEdge
from app.services.llm_client import LlmClient, get_llm_client

HIERARCHY_SYSTEM = """You build a semantic parent-child hierarchy for document sections.
Return ONLY valid JSON:
{
  "edges": [{"parent_id": "node_chunk_01", "child_id": "node_chunk_02"}],
  "roots": ["node_chunk_01"]
}

Rules:
- Use ONLY the provided node_ids.
- parent_id and child_id must be different nodes.
- roots are top-level nodes with no parent.
- edges represent topic containment (parent is broader, child is subtopic).
- Every node except roots must appear exactly once as child_id.
- No cycles. Form a forest of trees.
- If sections are sequential peers, chain them: parent earlier, child later.
"""


class HierarchyValidationError(Exception):
    pass


def build_hierarchy(
    nodes: dict[str, dict],
    client: LlmClient | None = None,
) -> tuple[list[TreeEdge], list[str]]:
    client = client or get_llm_client()
    node_ids = set(nodes.keys())

    if not node_ids:
        return [], []

    if len(node_ids) == 1:
        only = next(iter(node_ids))
        return [], [only]

    summaries = [
        {
            "node_id": node_id,
            "heading": data["heading"],
            "preview": data["full_chunk_text"][:200],
        }
        for node_id, data in nodes.items()
    ]
    user = json.dumps({"nodes": summaries}, ensure_ascii=False)
    result = client.complete_json(HIERARCHY_SYSTEM, user, max_tokens=8192)

    edges = _sanitize_edges(
        [
            TreeEdge(parent_id=e["parent_id"], child_id=e["child_id"])
            for e in result.get("edges", [])
        ],
        node_ids,
    )
    roots = list(result.get("roots", []))

    try:
        _validate_hierarchy(node_ids, edges, roots)
        child_ids = {e.child_id for e in edges}
        roots = [n for n in sorted(node_ids) if n not in child_ids]
        return edges, roots
    except HierarchyValidationError:
        return _linear_hierarchy(node_ids)


def _sanitize_edges(edges: list[TreeEdge], node_ids: set[str]) -> list[TreeEdge]:
    seen_children: set[str] = set()
    clean: list[TreeEdge] = []
    for edge in edges:
        if edge.parent_id not in node_ids or edge.child_id not in node_ids:
            continue
        if edge.parent_id == edge.child_id:
            continue
        if edge.child_id in seen_children:
            continue
        seen_children.add(edge.child_id)
        clean.append(edge)
    return clean


def _linear_hierarchy(node_ids: set[str]) -> tuple[list[TreeEdge], list[str]]:
    ordered = sorted(node_ids)
    edges = [
        TreeEdge(parent_id=ordered[i], child_id=ordered[i + 1])
        for i in range(len(ordered) - 1)
    ]
    return edges, [ordered[0]]


def _validate_hierarchy(
    node_ids: set[str],
    edges: list[TreeEdge],
    roots: list[str],
) -> None:
    if not node_ids:
        return

    for edge in edges:
        if edge.parent_id not in node_ids or edge.child_id not in node_ids:
            raise HierarchyValidationError("Edge references unknown node_id")
        if edge.parent_id == edge.child_id:
            raise HierarchyValidationError("Self-referencing edge detected")

    child_ids = {e.child_id for e in edges}
    parent_ids = {e.parent_id for e in edges}

    if len(child_ids) != len(edges):
        raise HierarchyValidationError("Node has multiple parents")

    computed_roots = [n for n in node_ids if n not in child_ids]
    if not roots:
        roots = computed_roots
    elif set(roots) != set(computed_roots):
        roots = computed_roots

    if not roots:
        raise HierarchyValidationError("No root nodes found")

    adjacency: dict[str, list[str]] = {n: [] for n in node_ids}
    for edge in edges:
        adjacency[edge.parent_id].append(edge.child_id)

    visiting: set[str] = set()
    visited: set[str] = set()

    def dfs(node: str) -> None:
        if node in visiting:
            raise HierarchyValidationError("Cycle detected in hierarchy")
        if node in visited:
            return
        visiting.add(node)
        for child in adjacency.get(node, []):
            dfs(child)
        visiting.remove(node)
        visited.add(node)

    for root in roots:
        dfs(root)

    unreachable = node_ids - visited
    if unreachable:
        for node in sorted(unreachable):
            roots.append(node)
            dfs(node)
