#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ENV_FILE:-$ROOT/.env}"
TARGET="${1:-runtime}"

read_env() {
  local key="$1"
  local fallback="$2"
  local value=""
  if [[ -f "$ENV_FILE" ]]; then
    value="$(sed -n "s/^${key}=//p" "$ENV_FILE" | tail -n 1)"
  fi
  printf '%s' "${value:-$fallback}"
}

download() {
  local url="$1"
  local path="$2"
  local sha256="$3"

  mkdir -p "$(dirname "$path")"
  if [[ ! -f "$path" ]]; then
    echo "Downloading $(basename "$path")..."
    curl -fL --retry 3 --retry-delay 2 "$url" -o "$path.part"
    echo "$sha256  $path.part" | sha256sum -c -
    mv "$path.part" "$path"
  fi

  echo "$sha256  $path" | sha256sum -c -
}

MODELS_DIR="$(read_env LLAMA_MODELS_DIR ./models)"
if [[ "$MODELS_DIR" != /* ]]; then
  MODELS_DIR="$ROOT/${MODELS_DIR#./}"
fi

LLM_FILE="$(read_env LLAMA_MODEL_FILE qwen3.5-2b-function-calling-xlam.q4_k_m.gguf)"
EMBEDDING_FILE="$(read_env EMBEDDING_MODEL_FILE Qwen3-Embedding-0.6B-Q8_0.gguf)"
RERANKER_FILE="$(read_env RERANKER_MODEL_FILE qwen3-reranker-0.6b-q8_0.gguf)"

if [[ "$TARGET" == "runtime" || "$TARGET" == "all" ]]; then
  download \
    "https://huggingface.co/ermiaazarkhalili/Qwen3.5-2B-Function-Calling-xLAM-GGUF/resolve/main/qwen3.5-2b-function-calling-xlam.q4_k_m.gguf?download=true" \
    "$MODELS_DIR/$LLM_FILE" \
    "0d5b45ec3d3b85184e16330a2239056dd768c713843682fe5d5801b5c13fbc0b"

  download \
    "https://huggingface.co/Qwen/Qwen3-Embedding-0.6B-GGUF/resolve/main/Qwen3-Embedding-0.6B-Q8_0.gguf?download=true" \
    "$MODELS_DIR/$EMBEDDING_FILE" \
    "06507c7b42688469c4e7298b0a1e16deff06caf291cf0a5b278c308249c3e439"
fi

if [[ "$TARGET" == "reranker" || "$TARGET" == "all" ]]; then
  download \
    "https://huggingface.co/ggml-org/Qwen3-Reranker-0.6B-Q8_0-GGUF/resolve/main/qwen3-reranker-0.6b-q8_0.gguf?download=true" \
    "$MODELS_DIR/$RERANKER_FILE" \
    "22c9979ce4fbcdc5acdc310c6641c32797eff1aa980b8f7a2db8a8ea23429a48"
fi

if [[ "$TARGET" != "runtime" && "$TARGET" != "reranker" && "$TARGET" != "all" ]]; then
  echo "usage: $0 [runtime|reranker|all]" >&2
  exit 2
fi
