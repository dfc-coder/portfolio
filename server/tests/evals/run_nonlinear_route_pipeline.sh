#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="${ENV_FILE:-$ROOT/.env}"
COMPOSE_FILE="${COMPOSE_FILE:-$ROOT/compose.yaml}"
ARTIFACT="${ROUTE_V5_ARTIFACT:-$ROOT/artifacts/business-route-v5.json}"
TMP_DIR="${ROUTE_V5_TMP_DIR:-/tmp/portfolio-routes-v5}"

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
  echo "ROUTE_V5_ARTIFACT must live under $ROOT so the eval container can read it" >&2
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
embed_split train_oos
embed_split validation

PYTHONPATH="$ROOT" uv run --with scikit-learn python tests/evals/train_nonlinear_route_classifier.py \
  --train-vectors "$TMP_DIR/train-vectors.json" \
  --oos-vectors "$TMP_DIR/train_oos-vectors.json" \
  --validation-vectors "$TMP_DIR/validation-vectors.json" \
  --train-cases tests/evals/intents/train.jsonl \
  --oos-cases tests/evals/intents/train_oos.jsonl \
  --output "$ARTIFACT"

run_eval() {
  local cases="$1"
  echo "== Evaluating $cases =="
  "${COMPOSE[@]}" run --rm --no-deps \
    -v "$ROOT:/workspace:Z" \
    -w /workspace \
    -e PYTHONPATH=/workspace \
    api python tests/evals/run_nonlinear_route_eval.py \
    --cases "tests/evals/intents/${cases}.jsonl" \
    --model "${ARTIFACT#$ROOT/}" \
    --strict
}

run_eval challenge
run_eval blind_test

echo "Nonlinear route candidate passed challenge and historical blind regression."
echo "Frozen artifact: $ARTIFACT"
sha256sum "$ARTIFACT"
