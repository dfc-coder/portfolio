#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

MODEL_FILE="${1:-}"
MODEL_LABEL="${2:-}"
FAMILY="${3:-}"
OUTPUT="${4:-}"

if [[ -z "$MODEL_FILE" || -z "$MODEL_LABEL" || -z "$FAMILY" || -z "$OUTPUT" ]]; then
  echo "Usage: bash scripts/run_family_model_diagnostic.sh <model-file.gguf> <model-label> <qwen35|gemma4> <output.json>" >&2
  exit 2
fi

if [[ "$FAMILY" != "qwen35" && "$FAMILY" != "gemma4" ]]; then
  echo "Unsupported family: $FAMILY" >&2
  exit 2
fi

if [[ ! -f .env ]]; then
  echo "Missing $ROOT/.env" >&2
  exit 2
fi

REQUIRED_EVAL_FILES=(
  tests/evals/run_family_model_selection.py
  tests/evals/run_family_model_diagnostic.py
  tests/evals/run_model_diagnostic.py
  tests/evals/scheduling_turn_cases.jsonl
  tests/evals/cases.jsonl
  tests/evals/business_response_cases.jsonl
)
for required in "${REQUIRED_EVAL_FILES[@]}"; do
  if [[ ! -f "$required" ]]; then
    echo "Missing benchmark dependency: $ROOT/$required" >&2
    echo "Run: git pull" >&2
    exit 2
  fi
done

set -a
# shellcheck disable=SC1091
source .env
set +a

ENGINE="${CONTAINER_ENGINE:-}"
if [[ -z "$ENGINE" ]]; then
  if command -v podman >/dev/null 2>&1; then
    ENGINE=podman
  elif command -v docker >/dev/null 2>&1; then
    ENGINE=docker
  else
    echo "Podman or Docker is required." >&2
    exit 2
  fi
fi

MODEL_DIR="${LLAMA_MODELS_DIR:-./models}"
if [[ "$MODEL_DIR" != /* ]]; then
  MODEL_DIR="$ROOT/$MODEL_DIR"
fi
if [[ ! -f "$MODEL_DIR/$MODEL_FILE" ]]; then
  echo "Model not found: $MODEL_DIR/$MODEL_FILE" >&2
  exit 2
fi

IMAGE="${LLAMA_IMAGE:-ghcr.io/ggml-org/llama.cpp:server}"
PORT="${BENCHMARK_PORT:-18080}"
GPU_LAYERS="${BENCHMARK_N_GPU_LAYERS:-${LLAMA_N_GPU_LAYERS:-0}}"
NAME="portfolio-family-diagnostic-$$"
CTX=16384

cleanup() {
  "$ENGINE" rm -f "$NAME" >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

SERVER_EXTRA_ARGS=()
if [[ "$FAMILY" == "qwen35" ]]; then
  # Exact Unsloth Qwen3.5 small-model non-thinking/general-task configuration.
  SERVER_EXTRA_ARGS+=(
    --temp 0.7
    --top-p 0.8
    --top-k 20
    --min-p 0.0
    --chat-template-kwargs '{"enable_thinking":false}'
  )
else
  # Exact Unsloth Gemma 4 standardized sampling recommendation.
  # Thinking remains disabled because the benchmark prompts do not include <|think|>.
  SERVER_EXTRA_ARGS+=(
    --temp 1.0
    --top-p 0.95
    --top-k 64
  )
fi

echo "Starting isolated llama.cpp family benchmark"
echo "Model:  $MODEL_FILE"
echo "Label:  $MODEL_LABEL"
echo "Family: $FAMILY"
echo "Port:   $PORT"
echo "Ctx:    $CTX"
if [[ "$FAMILY" == "qwen35" ]]; then
  echo "Profile: Unsloth Qwen3.5 small / instruct non-thinking / general tasks"
  echo "Params:  temp=0.7 top_p=0.8 top_k=20 min_p=0.0 presence_penalty=1.5 repeat_penalty=1.0"
  echo "Thinking: false"
else
  echo "Profile: Unsloth Gemma 4 standardized sampling"
  echo "Params:  temp=1.0 top_p=0.95 top_k=64"
  echo "Thinking: false (no <|think|> token in system prompt)"
fi

echo "Protocol: fail-fast model selection (no x5 repetitions)"

"$ENGINE" run -d --rm \
  --name "$NAME" \
  -p "127.0.0.1:${PORT}:8080" \
  -v "$MODEL_DIR:/models:ro,Z" \
  "$IMAGE" \
  -m "/models/$MODEL_FILE" \
  --alias benchmark-model \
  --host 0.0.0.0 \
  --port 8080 \
  --ctx-size "$CTX" \
  --parallel 1 \
  --cache-prompt \
  --jinja \
  "${SERVER_EXTRA_ARGS[@]}" \
  --n-predict 512 \
  --n-gpu-layers "$GPU_LAYERS" >/dev/null

printf "Waiting for benchmark model"
for _ in $(seq 1 180); do
  if curl -fsS "http://127.0.0.1:${PORT}/health" >/dev/null 2>&1; then
    echo " ready"
    break
  fi
  printf "."
  sleep 1
done

if ! curl -fsS "http://127.0.0.1:${PORT}/health" >/dev/null 2>&1; then
  echo
  echo "Benchmark model did not become ready." >&2
  "$ENGINE" logs "$NAME" >&2 || true
  exit 2
fi

mkdir -p "$(dirname "$OUTPUT")"
PYTHONPATH=. uv run python tests/evals/run_family_model_selection.py \
  --base-url "http://127.0.0.1:${PORT}" \
  --model benchmark-model \
  --model-label "$MODEL_LABEL" \
  --family "$FAMILY" \
  --output "$OUTPUT"
echo "Report: $OUTPUT"
