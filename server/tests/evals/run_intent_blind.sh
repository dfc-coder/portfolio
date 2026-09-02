#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="${ENV_FILE:-$ROOT/.env}"
COMPOSE_FILE="${COMPOSE_FILE:-$ROOT/compose.yaml}"
ARTIFACT="${ROUTE_ARTIFACT:-$ROOT/artifacts/business-route-v4.json}"

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
  echo "frozen route artifact not found: $ARTIFACT" >&2
  echo "run make eval-intents-challenge first and freeze the passing artifact" >&2
  exit 1
fi

if [[ "$ARTIFACT" != "$ROOT"/* ]]; then
  echo "ROUTE_ARTIFACT must live under $ROOT so the eval container can read it" >&2
  exit 1
fi

COMPOSE=("$ENGINE" compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE")
ARTIFACT_SHA_BEFORE="$(sha256sum "$ARTIFACT" | awk '{print $1}')"

echo "Frozen artifact: $ARTIFACT"
echo "Artifact SHA256: $ARTIFACT_SHA_BEFORE"
echo "No training or threshold calibration will run during blind evaluation."

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
  api python tests/evals/run_intent_eval.py \
  --cases tests/evals/intents/blind_test.jsonl \
  --model "${ARTIFACT#$ROOT/}" \
  --strict
EVAL_STATUS=$?
set -e

ARTIFACT_SHA_AFTER="$(sha256sum "$ARTIFACT" | awk '{print $1}')"
if [[ "$ARTIFACT_SHA_AFTER" != "$ARTIFACT_SHA_BEFORE" ]]; then
  echo "frozen route artifact changed during blind evaluation" >&2
  echo "before: $ARTIFACT_SHA_BEFORE" >&2
  echo "after:  $ARTIFACT_SHA_AFTER" >&2
  exit 2
fi

echo "Artifact unchanged: $ARTIFACT_SHA_AFTER"
exit "$EVAL_STATUS"
