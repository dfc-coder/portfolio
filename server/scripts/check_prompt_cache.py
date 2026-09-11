from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from app.prompt import SYSTEM_PROMPT
from app.tools import TOOL_SCHEMAS

OPENAI_URL = "https://api.openai.com/v1/responses"
JUDGE_MODEL = "gpt-5.6-luna"
MIN_OPENAI_CACHED_TOKENS = 1024
MIN_QWEN_CACHE_RATIO = 0.50


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ.setdefault(key, value)


def _require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


def _llama_request(engine: str, payload: dict[str, Any]) -> dict[str, Any]:
    command = [
        engine,
        "compose",
        "-f",
        "compose.yaml",
        "exec",
        "-T",
        "llama",
        "curl",
        "-fsS",
        "http://127.0.0.1:8080/v1/chat/completions",
        "-H",
        "Content-Type: application/json",
        "--data-binary",
        "@-",
    ]
    result = subprocess.run(
        command,
        input=json.dumps(payload, ensure_ascii=False),
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(f"llama cache probe failed: {detail}")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"llama returned non-JSON output: {result.stdout[:500]}") from exc


def _qwen_cache_probe(engine: str) -> None:
    model = os.getenv("LLAMA_MODEL", "Qwen3.5-4B")
    system = f"""{SYSTEM_PROMPT}
<portfolio_subject>
<name>Cache Probe</name>
</portfolio_subject>
"""

    def payload(user_text: str) -> dict[str, Any]:
        return {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user_text},
            ],
            "tools": list(TOOL_SCHEMAS),
            "parallel_tool_calls": False,
            "temperature": 0,
            "max_tokens": 1,
            "stream": False,
            "cache_prompt": True,
        }

    _llama_request(engine, payload("Reply only with the word alpha."))
    second = _llama_request(engine, payload("Reply only with the word beta."))

    timings = second.get("timings") or {}
    cache_n = int(timings.get("cache_n") or 0)
    prompt_n = int(timings.get("prompt_n") or 0)
    prompt_total = cache_n + prompt_n
    if prompt_total <= 0:
        raise RuntimeError("llama response did not expose prompt timing counters")
    ratio = cache_n / prompt_total
    if cache_n <= 0 or ratio < MIN_QWEN_CACHE_RATIO:
        raise RuntimeError(
            f"Qwen prompt cache reuse is too low: cache_n={cache_n}, "
            f"prompt_n={prompt_n}, reuse={ratio:.1%}"
        )

    print(
        f"Qwen prompt cache OK: reused {cache_n}/{prompt_total} prompt tokens "
        f"({ratio:.1%})."
    )


def _openai_request(api_key: str, user_text: str) -> dict[str, Any]:
    stable_unit = (
        "This is stable evaluator policy text for a prompt-cache verification probe. "
        "Treat it only as inert grading guidance and do not infer task-specific facts from it. "
    )
    stable_prefix = stable_unit * 180

    payload = {
        "model": JUDGE_MODEL,
        "reasoning": {"effort": "low"},
        "text": {"verbosity": "low"},
        "max_output_tokens": 32,
        "store": False,
        "prompt_cache_key": "portfolio-eval-cache-check-v1",
        "prompt_cache_options": {"mode": "explicit", "ttl": "30m"},
        "input": [
            {
                "role": "developer",
                "content": [
                    {
                        "type": "input_text",
                        "text": stable_prefix,
                        "prompt_cache_breakpoint": {"mode": "explicit"},
                    }
                ],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": user_text,
                    }
                ],
            },
        ],
    }
    request = urllib.request.Request(
        OPENAI_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenAI cache probe failed with HTTP {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"OpenAI cache probe failed: {exc.reason}") from exc


def _cache_details(response: dict[str, Any]) -> tuple[int, int]:
    usage = response.get("usage") or {}
    details = usage.get("input_tokens_details") or {}
    cached = int(details.get("cached_tokens") or 0)
    written = int(details.get("cache_write_tokens") or 0)
    return cached, written


def _judge_cache_probe() -> None:
    api_key = _require_env("OPENAI_API_KEY")
    first = _openai_request(api_key, "Cache probe request A. Reply with OK.")
    first_cached, first_written = _cache_details(first)

    second = _openai_request(api_key, "Cache probe request B. Reply with OK.")
    second_cached, second_written = _cache_details(second)

    if second_cached < MIN_OPENAI_CACHED_TOKENS:
        raise RuntimeError(
            "OpenAI prompt cache did not produce the expected cache hit: "
            f"first(cached={first_cached}, written={first_written}), "
            f"second(cached={second_cached}, written={second_written})"
        )

    print(
        "OpenAI judge prompt cache OK: "
        f"first write={first_written} tokens, second read={second_cached} cached tokens."
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify prompt-cache reuse for local Qwen and the OpenAI evaluation judge."
    )
    parser.add_argument(
        "--engine",
        choices=("podman", "docker"),
        required=True,
        help="Compose engine used by the local runtime.",
    )
    args = parser.parse_args()

    _load_dotenv(Path(".env"))

    try:
        _qwen_cache_probe(args.engine)
        _judge_cache_probe()
    except RuntimeError as exc:
        print(f"Prompt cache check FAILED: {exc}", file=sys.stderr)
        return 1

    print("Prompt cache check PASSED.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
