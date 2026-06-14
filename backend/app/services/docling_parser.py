from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path


class DoclingParseError(Exception):
    pass


def parse_pdf(pdf_bytes: bytes) -> str:
    # Let Docling manage its own models; ignore any DOCLING_ARTIFACTS_PATH in .env.
    os.environ.pop("DOCLING_ARTIFACTS_PATH", None)

    try:
        from docling.document_converter import DocumentConverter
    except ImportError as exc:
        raise DoclingParseError(
            "Docling is not installed. Run: pip3 install -r backend/requirements.txt"
        ) from exc

    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(pdf_bytes)
            tmp_path = Path(tmp.name)

        result = DocumentConverter().convert(str(tmp_path))
        text = result.document.export_to_text()
    except Exception as exc:
        raise DoclingParseError(f"Failed to parse PDF with Docling: {exc}") from exc
    finally:
        if tmp_path is not None and tmp_path.exists():
            tmp_path.unlink(missing_ok=True)

    return _clean_text(text)


def _clean_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
