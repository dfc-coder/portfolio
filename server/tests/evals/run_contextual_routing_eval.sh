#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

if command -v podman >/dev/null 2>&1; then
  ENGINE=podman
elif command -v docker >/dev/null 2>&1; then
  ENGINE=docker
else
  echo "Podman or Docker is required." >&2
  exit 1
fi

"$ENGINE" compose up -d embedding

"$ENGINE" compose run --rm --no-deps \
  -v "$ROOT:/workspace:Z" \
  -w /workspace \
  -e PYTHONPATH=/workspace \
  api \
  python -u tests/evals/run_contextual_routing_eval.py "$@"
