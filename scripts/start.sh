#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH=backend
python -m cyberkingdoms.cli serve --host "${HOST:-127.0.0.1}" --port "${PORT:-8080}"
