#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="${ENV_FILE:-$ROOT/.env}"
COMPOSE_FILE="${COMPOSE_FILE:-$ROOT/compose.yaml}"
ARTIFACT="${ROUTE_ARTIFACT:-$ROOT/artifacts/business-route-v2.json}"
TMP_DIR="${ROUTE_TMP_DIR:-/tmp/portfolio-routes}"

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

if [[ "$ARTIFACT" != "$ROOT"/* ]]; then
  echo "ROUTE_ARTIFACT must live under $ROOT so the eval container can read it" >&2
  exit 1
fi

mkdir -p "$TMP_DIR" "$(dirname "$ARTIFACT")"
COMPOSE=("$ENGINE" compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE")

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

embed_split() {
  local split="$1"
  "${COMPOSE[@]}" run --rm --no-deps \
    -v "$ROOT:/workspace:Z" \
    -w /workspace \
    -e PYTHONPATH=/workspace \
    api python tests/evals/embed_intent_cases.py \
    --cases "tests/evals/intents/${split}.jsonl" \
    > "$TMP_DIR/${split}-vectors.json"
}

embed_split train
embed_split validation

PYTHONPATH="$ROOT" uv run --with scikit-learn python tests/evals/train_intent_classifier.py \
  --train-vectors "$TMP_DIR/train-vectors.json" \
  --validation-vectors "$TMP_DIR/validation-vectors.json" \
  --train-cases tests/evals/intents/train.jsonl \
  --output "$ARTIFACT"

"${COMPOSE[@]}" run --rm --no-deps \
  -v "$ROOT:/workspace:Z" \
  -w /workspace \
  -e PYTHONPATH=/workspace \
  api python tests/evals/run_intent_eval.py \
  --cases tests/evals/intents/challenge.jsonl \
  --model "${ARTIFACT#$ROOT/}"

if [[ "${1:-}" == "--blind" ]]; then
  "${COMPOSE[@]}" run --rm --no-deps \
    -v "$ROOT:/workspace:Z" \
    -w /workspace \
    -e PYTHONPATH=/workspace \
    api python tests/evals/run_intent_eval.py \
    --cases tests/evals/intents/blind_test.jsonl \
    --model "${ARTIFACT#$ROOT/}" \
    --strict
fi
