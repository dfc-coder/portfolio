from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from openai import AsyncOpenAI

from .prompt import build_classifier_messages


class Route(StrEnum):
    GENERAL = "general"
    PORTFOLIO = "portfolio"
    DATETIME = "datetime"
    REMINDER = "reminder"


@dataclass(frozen=True)
class Dispatch:
    routes: tuple[Route, ...]
    raw: str


async def classify(
    chat: AsyncOpenAI,
    *,
    model: str,
    subject: str,
    message: str,
    context: list[dict[str, Any]],
) -> Dispatch:
    response = await chat.chat.completions.create(
        model=model,
        messages=build_classifier_messages(subject, context, message),
        temperature=0.0,
        top_p=1.0,
        max_tokens=64,
        stream=False,
        extra_body={"top_k": 1, "min_p": 0.0, "repeat_penalty": 1.0},
    )

    choices = getattr(response, "choices", None) or []
    if not choices:
        raise RuntimeError("classifier returned no choices")

    content = getattr(choices[0].message, "content", None)
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError("classifier returned an empty response")

    payload = _parse_object(content)
    raw_routes = payload.get("routes")
    if not isinstance(raw_routes, list) or not raw_routes:
        raise RuntimeError("classifier response must contain a non-empty routes array")

    routes: list[Route] = []
    for value in raw_routes:
        if not isinstance(value, str):
            raise RuntimeError("classifier route must be a string")
        try:
            route = Route(value)
        except ValueError as exc:
            raise RuntimeError(f"classifier returned unknown route: {value}") from exc
        if route in routes:
            raise RuntimeError(f"classifier returned duplicate route: {value}")
        routes.append(route)

    return Dispatch(routes=tuple(routes), raw=content)


def _parse_object(content: str) -> dict[str, Any]:
    value = content.strip()
    if value.startswith("```"):
        lines = value.splitlines()
        if len(lines) >= 3 and lines[-1].strip() == "```":
            value = "\n".join(lines[1:-1]).strip()
            if value.startswith("json"):
                value = value[4:].lstrip()

    try:
        payload = json.loads(value)
    except json.JSONDecodeError as exc:
        raise RuntimeError("classifier returned invalid JSON") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("classifier response must be a JSON object")
    return payload
