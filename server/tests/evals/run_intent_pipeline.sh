#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="${ENV_FILE:-$ROOT/.env}"
COMPOSE_FILE="${COMPOSE_FILE:-$ROOT/compose.yaml}"
ARTIFACT="${INTENT_ARTIFACT:-$ROOT/artifacts/intent-router-v1.json}"
TMP_DIR="${INTENT_TMP_DIR:-/tmp/portfolio-intents}"

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

mkdir -p "$TMP_DIR" "$(dirname "$ARTIFACT")"
COMPOSE=("$ENGINE" compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE")

cd "$ROOT"
"${COMPOSE[@]}" up -d embedding

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

uv run --with scikit-learn python tests/evals/train_intent_classifier.py \
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
