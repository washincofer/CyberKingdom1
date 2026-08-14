#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-.}"
if [[ ! -f "$ROOT/web/index.html" ]]; then
  echo "Erro: execute apontando para a raiz do CyberKingdom1." >&2
  exit 1
fi
cp "$ROOT/web/index.html" "$ROOT/web/index_technical_v0.1.html"
cp "$(cd "$(dirname "$0")" && pwd)/web/index.html" "$ROOT/web/index.html"
mkdir -p "$ROOT/docs"
cp "$(cd "$(dirname "$0")" && pwd)/docs/VS001_RECREATED_FREEZE.md" "$ROOT/docs/VS001_RECREATED_FREEZE.md"
echo "VS-001 Recreated Integrated Candidate 01 aplicada."
