#!/usr/bin/env bash
# One-time setup: install docling and prefetch HuggingFace models for offline use.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
VENV_DIR="${BACKEND_DIR}/.venv"
MODELS_DIR="${HOME}/.cache/docling/models"

echo "==> Docling setup"
echo "    Backend: ${BACKEND_DIR}"
echo "    Models:  ${MODELS_DIR}"

if [[ ! -d "${VENV_DIR}" ]]; then
  echo "==> Creating virtualenv"
  python3 -m venv "${VENV_DIR}"
fi

# shellcheck disable=SC1091
source "${VENV_DIR}/bin/activate"

pip3 install --upgrade pip setuptools wheel -q
pip3 install -r "${BACKEND_DIR}/requirements.txt" -q

python3 -c "from docling.document_converter import DocumentConverter; print('docling OK')"

mkdir -p "${MODELS_DIR}"
docling-tools models download layout tableformer --output-dir "${MODELS_DIR}"

echo ""
echo "Add to backend/.env:"
echo "  DOCLING_ARTIFACTS_PATH=${MODELS_DIR}"
