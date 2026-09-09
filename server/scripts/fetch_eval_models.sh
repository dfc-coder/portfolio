#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ENV_FILE:-$ROOT/.env}"

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

LLM_FILE="$(read_env LLAMA_MODEL_FILE Qwen3.5-2B-UD-Q6_K_XL.gguf)"
EMBEDDING_FILE="$(read_env EMBEDDING_MODEL_FILE Qwen3-Embedding-0.6B-Q8_0.gguf)"
RERANKER_FILE="$(read_env RERANKER_MODEL_FILE qwen3-reranker-0.6b-q8_0.gguf)"

download \
  "https://huggingface.co/unsloth/Qwen3.5-2B-GGUF/resolve/main/Qwen3.5-2B-UD-Q6_K_XL.gguf?download=true" \
  "$MODELS_DIR/$LLM_FILE" \
  "2f956e57c27b3f257916825d9d3bc174269f3df9c6fcf87a64da666c0e7a518a"

download \
  "https://huggingface.co/Qwen/Qwen3-Embedding-0.6B-GGUF/resolve/main/Qwen3-Embedding-0.6B-Q8_0.gguf?download=true" \
  "$MODELS_DIR/$EMBEDDING_FILE" \
  "06507c7b42688469c4e7298b0a1e16deff06caf291cf0a5b278c308249c3e439"

download \
  "https://huggingface.co/ggml-org/Qwen3-Reranker-0.6B-Q8_0-GGUF/resolve/main/qwen3-reranker-0.6b-q8_0.gguf?download=true" \
  "$MODELS_DIR/$RERANKER_FILE" \
  "22c9979ce4fbcdc5acdc310c6641c32797eff1aa980b8f7a2db8a8ea23429a48"
