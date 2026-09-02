#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="${ENV_FILE:-$ROOT/.env}"
COMPOSE_FILE="${COMPOSE_FILE:-$ROOT/compose.yaml}"
ARTIFACT="${ROUTE_V5_ARTIFACT:-$ROOT/artifacts/business-route-v5.json}"

if command -v podman >/dev/null 2>&1; then
  ENGINE=podman
elif command -v docker >/dev/null 2>&1; then
  ENGINE=docker
else
  echo "podman or docker is required" >&2
  exit 1
fi

if [[ ! -f "$ENV_FILE" ]]; then
  echo "missing env file: $ENV_FILE" >&2
  exit 1
fi
if [[ ! -f "$ARTIFACT" ]]; then
  echo "frozen nonlinear route artifact is missing: $ARTIFACT" >&2
  echo "Run the nonlinear challenge/regression pipeline first; do not retrain from this target." >&2
  exit 1
fi

COMPOSE=("$ENGINE" compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE")
BEFORE="$(sha256sum "$ARTIFACT" | awk '{print $1}')"

echo "Frozen artifact: $ARTIFACT"
echo "Artifact SHA256: $BEFORE"
echo "No training or threshold calibration will run during final holdout evaluation."

cd "$ROOT"
"${COMPOSE[@]}" build api
"${COMPOSE[@]}" up -d embedding

for attempt in $(seq 1 60); do
  if "${COMPOSE[@]}" exec -T embedding \
    curl -fsS http://127.0.0.1:8081/health >/dev/null 2>&1; then
    break
  fi
  if [[ "$attempt" -eq 60 ]]; then
    echo "embedding service did not become ready" >&2
    exit 1
  fi
  sleep 1
done

set +e
"${COMPOSE[@]}" run --rm --no-deps \
  -v "$ROOT:/workspace:Z" \
  -w /workspace \
  -e PYTHONPATH=/workspace \
  api python tests/evals/run_nonlinear_route_eval.py \
  --cases tests/evals/intents/final_holdout_v2.jsonl \
  --model "${ARTIFACT#$ROOT/}" \
  --strict
STATUS=$?
set -e

AFTER="$(sha256sum "$ARTIFACT" | awk '{print $1}')"
if [[ "$BEFORE" != "$AFTER" ]]; then
  echo "ERROR: frozen artifact changed during final evaluation" >&2
  exit 1
fi

echo "Artifact unchanged: $AFTER"
exit "$STATUS"
