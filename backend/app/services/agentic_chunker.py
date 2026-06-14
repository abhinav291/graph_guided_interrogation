from __future__ import annotations

import json
import logging
import re

from app.config import get_settings
from app.services.llm_client import LlmClient, get_llm_client

logger = logging.getLogger(__name__)

CHUNK_TEST_MODE_MAX = 10


def estimate_source_chars_for_chunks(max_chunks: int, max_chunk_chars: int) -> int:
    """Upper-bound source length to feed the chunker for *max_chunks* outputs."""
    return max_chunks * max_chunk_chars


CHUNK_SYSTEM = """You are a document segmentation assistant.
Split the provided text into the next logical thematic chunk.

Rules:
- Return ONLY valid JSON with keys: "chunk" (string), "done" (boolean).
- "chunk" is the next sequential semantic block from the remaining text.
- Each chunk MUST be at most {max_chars} characters (Python len()). Count carefully.
- There is NO minimum chunk size.
- Do NOT skip content. Do NOT repeat already-consumed text.
- Set "done": true only when no meaningful text remains after this chunk.
- Preserve sentence boundaries where possible; never cut mid-word if avoidable.
- If the next logical section is longer than {max_chars} chars, split at the nearest sentence boundary under the limit.
- SKIP (return empty chunk "") for: table of contents, index pages, page-number lists, headers/footers, OCR gibberish, or any block without coherent prose sentences.
"""


class ChunkLimitExceededError(Exception):
    pass


def _hard_split(text: str, max_chars: int) -> tuple[str, str]:
    """Deterministic split when the LLM exceeds max_chars. Returns (head, tail)."""
    text = text.strip()
    if len(text) <= max_chars:
        return text, ""

    window = text[:max_chars]
    min_size = max(max_chars // 4, 1)

    for sep in ("\n\n", "\n", ". ", "? ", "! ", "; ", ", ", " "):
        idx = window.rfind(sep)
        if idx >= min_size:
            cut = idx + len(sep)
            head = text[:cut].strip()
            tail = text[cut:].strip()
            if head:
                return head, tail

    head = window.strip()
    tail = text[max_chars:].strip()
    return head, tail


def _advance_remaining(remaining: str, chunk_text: str) -> str:
    if remaining.startswith(chunk_text):
        return remaining[len(chunk_text) :].lstrip()
    idx = remaining.find(chunk_text)
    if idx >= 0:
        return remaining[idx + len(chunk_text) :].lstrip()
    return remaining[len(chunk_text) :].lstrip()


def _is_incoherent_chunk(text: str) -> bool:
    """Heuristic filter for index pages, TOC, and OCR gibberish."""
    text = text.strip()
    if len(text) < 40:
        return True

    lower = text.lower()
    if any(
        marker in lower
        for marker in (
            "table of contents",
            "contents\n",
            "\nindex\n",
            "index of",
        )
    ):
        return True

    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        return True

    # Dot leaders and page-number index lines (e.g. "Chapter 1 .... 5")
    dot_leader_lines = sum(1 for ln in lines if re.search(r"\.{4,}\s*\d+\s*$", ln))
    if dot_leader_lines >= 2 or (
        len(lines) >= 3 and dot_leader_lines / len(lines) >= 0.4
    ):
        return True

    # Mostly numbers, punctuation, or very short tokens
    words = re.findall(r"[A-Za-z]{3,}", text)
    if len(words) < 8:
        return True

    alpha_chars = sum(1 for c in text if c.isalpha())
    if alpha_chars / max(len(text), 1) < 0.35:
        return True

    # Lines that are mostly digits (page lists)
    numeric_lines = sum(
        1
        for ln in lines
        if len(re.sub(r"[\d\s.\-–—]", "", ln)) <= 3 and re.search(r"\d", ln)
    )
    if len(lines) >= 4 and numeric_lines / len(lines) >= 0.5:
        return True

    return False


def agentic_chunk(
    text: str,
    client: LlmClient | None = None,
    *,
    max_chunks: int | None = None,
) -> list[str]:
    settings = get_settings()
    max_chars = settings.chunk_max_chars
    client = client or get_llm_client()

    chunks: list[str] = []
    remaining = text.strip()
    cursor = 0
    skip_streak = 0

    while remaining:
        if max_chunks is not None and len(chunks) >= max_chunks:
            break
        system = CHUNK_SYSTEM.format(max_chars=max_chars)
        user = json.dumps(
            {
                "cursor": cursor,
                "remaining_text": remaining[:8000],
                "remaining_length": len(remaining),
                "max_chars": max_chars,
            },
            ensure_ascii=False,
        )

        chunk_text: str | None = None
        done = False

        for attempt in range(3):
            result = client.complete_json(system, user, max_tokens=2048)
            candidate = str(result.get("chunk", "")).strip()
            done = bool(result.get("done", False))

            if not candidate:
                user = json.dumps(
                    {
                        "error": "Empty chunk returned",
                        "max_chars": max_chars,
                        "remaining_text": remaining[:8000],
                    },
                    ensure_ascii=False,
                )
                continue

            if len(candidate) > max_chars:
                user = json.dumps(
                    {
                        "error": f"Chunk length {len(candidate)} exceeds max {max_chars}",
                        "instruction": f"Return a shorter chunk under {max_chars} chars.",
                        "remaining_text": remaining[:8000],
                    },
                    ensure_ascii=False,
                )
                continue

            chunk_text = candidate
            break

        if chunk_text is None:
            chunk_text, tail = _hard_split(remaining, max_chars)
            remaining = tail
            logger.warning(
                "LLM chunk exceeded %d chars; used deterministic split (%d chars)",
                max_chars,
                len(chunk_text),
            )
            done = not remaining
        else:
            remaining = _advance_remaining(remaining, chunk_text)
            if len(chunk_text) > max_chars:
                chunk_text, overflow = _hard_split(chunk_text, max_chars)
                if overflow:
                    remaining = (overflow + " " + remaining).strip()

        if not chunk_text:
            raise ChunkLimitExceededError(
                "Unable to split document text into non-empty chunks."
            )

        if _is_incoherent_chunk(chunk_text):
            logger.info("Skipping incoherent chunk (%d chars)", len(chunk_text))
            skip_streak += 1
            if skip_streak > 25 or not remaining:
                break
            continue

        skip_streak = 0
        chunks.append(chunk_text)
        cursor += len(chunk_text)

        if max_chunks is not None and len(chunks) >= max_chunks:
            break

        if done or not remaining:
            break

    return chunks
