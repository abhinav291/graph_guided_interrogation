"""Export OpenAPI spec from FastAPI app to openapi.yaml."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.main import app  # noqa: E402


def main() -> None:
    spec = app.openapi()
    out_path = ROOT / "openapi.yaml"
    with out_path.open("w", encoding="utf-8") as f:
        yaml.dump(spec, f, sort_keys=False, allow_unicode=True, default_flow_style=False)
    json_path = ROOT / "openapi.json"
    with json_path.open("w", encoding="utf-8") as f:
        json.dump(spec, f, indent=2)
    print(f"Exported OpenAPI spec to {out_path}")


if __name__ == "__main__":
    main()
