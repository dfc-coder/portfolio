#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

MODEL_FILE="${1:-}"
MODEL_LABEL="${2:-}"
OUTPUT="${3:-}"

if [[ -z "$MODEL_FILE" || -z "$MODEL_LABEL" || -z "$OUTPUT" ]]; then
  echo "Usage: bash scripts/run_model_diagnostic.sh <model-file.gguf> <model-label> <output.json>" >&2
  exit 2
fi

if [[ ! -f .env ]]; then
  echo "Missing $ROOT/.env" >&2
  exit 2
fi

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
CTX="${BENCHMARK_CTX_SIZE:-8192}"
GPU_LAYERS="${BENCHMARK_N_GPU_LAYERS:-${LLAMA_N_GPU_LAYERS:-0}}"
NAME="portfolio-qwen-diagnostic-$$"

cleanup() {
  "$ENGINE" rm -f "$NAME" >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

echo "Starting isolated llama.cpp benchmark server"
echo "Model: $MODEL_FILE"
echo "Label: $MODEL_LABEL"
echo "Port:  $PORT"
echo "Mode:  reasoning OFF (agent structured-output benchmark)"

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
  --reasoning off \
  --n-predict 512 \
  --n-gpu-layers "$GPU_LAYERS" >/dev/null

printf "Waiting for benchmark model"
for _ in $(seq 1 120); do
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
PYTHONPATH=. uv run python tests/evals/run_model_diagnostic.py \
  --base-url "http://127.0.0.1:${PORT}" \
  --model benchmark-model \
  --model-label "$MODEL_LABEL" \
  --critical-repetitions "${CRITICAL_REPETITIONS:-3}" \
  --finalists "${DIAGNOSTIC_FINALISTS:-2}" \
  --profiles \
    project_current \
    unsloth_instruct_general \
    unsloth_instruct_reasoning \
    minimal_instruct_general \
    minimal_instruct_reasoning \
  --output "$OUTPUT"

echo "Report: $OUTPUT"
