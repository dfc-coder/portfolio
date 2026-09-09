from __future__ import annotations

import json
import logging
import time
from collections.abc import AsyncIterator
from typing import Any

from openai import AsyncOpenAI

from .portfolio import Portfolio
from .prompt import build_messages
from .tools import TOOLS, run_tool_call, tool_name
from .trace import TurnTrace, chunk_metadata, elapsed_ms, parse_json, utc_now

MAX_TOOL_ROUNDS = 6
MAX_CONTEXT_MESSAGES = 32
AgentEvent = tuple[str, dict[str, object]]

logger = logging.getLogger(__name__)


class Agent:
    def __init__(
        self,
        subject: str,
        chat: AsyncOpenAI,
        portfolio: Portfolio,
        *,
        model: str,
        temperature: float = 0.0,
        top_p: float = 1.0,
        top_k: int = 1,
        min_p: float = 0.0,
        presence_penalty: float = 0.0,
        repeat_penalty: float = 1.0,
        max_tokens: int = 256,
    ) -> None:
        self._subject = subject
        self._chat = chat
        self._portfolio = portfolio
        self._model = model
        self._temperature = temperature
        self._top_p = top_p
        self._top_k = top_k
        self._min_p = min_p
        self._presence_penalty = presence_penalty
        self._repeat_penalty = repeat_penalty
        self._max_tokens = max_tokens

    async def respond(
        self,
        message: str,
        context: list[dict[str, Any]],
        *,
        diagnostics: bool = False,
    ) -> AsyncIterator[AgentEvent]:
        tools = list(TOOLS)
        allowed_tool_names = {tool_name(tool) for tool in tools}
        messages = build_messages(
            self._subject,
            _trim_context(context),
            message,
        )

        generation = {
            "temperature": self._temperature,
            "top_p": self._top_p,
            "top_k": self._top_k,
            "min_p": self._min_p,
            "presence_penalty": self._presence_penalty,
            "repeat_penalty": self._repeat_penalty,
            "max_tokens": self._max_tokens,
            "parallel_tool_calls": len(tools) > 1,
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        trace = TurnTrace(
            message=message,
            context=context,
            model=self._model,
            generation=generation,
            tools=tools,
        )

        successful_calls: dict[tuple[str, str], dict[str, str]] = {}
        force_answer = False

        try:
            for round_number in range(1, MAX_TOOL_ROUNDS + 2):
                yield "status", {"phase": "model", "round": round_number}
                round_trace = trace.start_round(round_number, messages)
                started = time.perf_counter()

                extra_body: dict[str, object] = {
                    "top_k": self._top_k,
                    "min_p": self._min_p,
                    "repeat_penalty": self._repeat_penalty,
                }
                if diagnostics:
                    extra_body.update(
                        {
                            "verbose": True,
                            "timings_per_token": True,
                            "return_progress": True,
                        }
                    )

                request: dict[str, Any] = {
                    "model": self._model,
                    "messages": messages,
                    "temperature": self._temperature,
                    "top_p": self._top_p,
                    "presence_penalty": self._presence_penalty,
                    "max_tokens": self._max_tokens,
                    "stream": True,
                    "stream_options": {"include_usage": True},
                    "extra_body": extra_body,
                }
                if tools and not force_answer:
                    request["tools"] = tools
                    request["parallel_tool_calls"] = len(tools) > 1

                stream = await self._chat.chat.completions.create(**request)

                content: list[str] = []
                calls: dict[int, dict[str, str]] = {}
                finish_reason: str | None = None
                responding = False

                async for chunk in stream:
                    response_trace = round_trace["response"]
                    response_trace["chunk_count"] += 1
                    _record_chunk_metadata(response_trace, chunk_metadata(chunk))

                    choices = getattr(chunk, "choices", None) or []
                    if not choices:
                        continue

                    choice = choices[0]
                    response_trace["choice_index"] = getattr(choice, "index", 0)
                    if choice.finish_reason is not None:
                        finish_reason = choice.finish_reason
                        response_trace["finish_reason"] = finish_reason

                    delta = choice.delta
                    if getattr(delta, "role", None):
                        response_trace["role"] = delta.role
                    if getattr(delta, "reasoning_content", None):
                        response_trace["reasoning_content_present"] = True

                    text = delta.content or ""
                    tool_deltas = delta.tool_calls or []
                    if (text or tool_deltas) and response_trace["first_delta_ms"] is None:
                        response_trace["first_delta_ms"] = elapsed_ms(started)

                    if text:
                        if response_trace["first_text_ms"] is None:
                            response_trace["first_text_ms"] = elapsed_ms(started)
                        if not responding:
                            responding = True
                            yield "status", {
                                "phase": "responding",
                                "round": round_number,
                            }
                        content.append(text)
                        yield "token", {"text": text}

                    for call in tool_deltas:
                        item = calls.setdefault(
                            call.index,
                            {"id": "", "name": "", "arguments": ""},
                        )
                        if call.id:
                            item["id"] += call.id
                        if call.function:
                            if call.function.name:
                                item["name"] += call.function.name
                            if call.function.arguments:
                                item["arguments"] += call.function.arguments

                text = "".join(content)
                ordered_calls = [calls[index] for index in sorted(calls)]
                tool_names = [call["name"] for call in ordered_calls]

                response_trace = round_trace["response"]
                response_trace["content"] = text
                response_trace["finish_reason"] = finish_reason
                trace.finish_round(round_trace)

                logger.info(
                    "agent round=%s finish=%s tools=%s latency_ms=%d",
                    round_number,
                    finish_reason,
                    ",".join(tool_names) or "-",
                    int((time.perf_counter() - started) * 1000),
                )

                _validate_model_round(finish_reason, ordered_calls)
                _validate_allowed_calls(ordered_calls, allowed_tool_names)

                assistant_message = _assistant_message(text or None, ordered_calls)
                round_trace["assistant_message"] = assistant_message
                messages.append(assistant_message)

                if not ordered_calls:
                    if not text.strip():
                        raise RuntimeError("LLM returned an empty response")
                    returned_context = _trim_context(messages[1:])
                    yield "context", {"messages": returned_context}
                    if diagnostics:
                        yield "trace", trace.finish(
                            status="ok",
                            output=text,
                            context=returned_context,
                        )
                    return

                if round_number > MAX_TOOL_ROUNDS:
                    raise RuntimeError("tool loop limit reached")

                tool_traces: list[dict[str, object]] = []
                reused_count = 0

                for call in ordered_calls:
                    signature = _call_signature(call)
                    previous = successful_calls.get(signature)

                    if previous is not None:
                        result, tool_trace = _reuse_successful_result(call, previous)
                        reused_count += 1
                        yield "tool", {
                            "name": call["name"],
                            "state": "done",
                            "ok": True,
                            "reused": True,
                            "round": round_number,
                        }
                    else:
                        yield "tool", {
                            "name": call["name"],
                            "state": "running",
                            "round": round_number,
                        }
                        result, tool_trace = await _run_traced_tool(
                            call,
                            self._portfolio,
                        )
                        ok = _tool_ok(result)
                        yield "tool", {
                            "name": call["name"],
                            "state": "done",
                            "ok": ok,
                            "round": round_number,
                        }
                        if ok:
                            successful_calls[signature] = result

                    messages.append(result)
                    tool_traces.append(tool_trace)

                round_trace["tool_calls"] = tool_traces
                force_answer = reused_count == len(ordered_calls)

            raise RuntimeError("tool loop limit reached")
        except Exception as exc:
            if diagnostics:
                yield "trace", trace.finish(
                    status="error",
                    error={"type": type(exc).__name__, "message": str(exc)},
                )
            raise


async def _run_traced_tool(
    call: dict[str, str],
    portfolio: Portfolio,
) -> tuple[dict[str, str], dict[str, object]]:
    started = time.perf_counter()
    started_at = utc_now()
    result = await run_tool_call(
        call["id"],
        call["name"],
        call["arguments"],
        portfolio,
    )
    finished_at = utc_now()
    content = result.get("content", "")
    return result, {
        "id": call["id"],
        "name": call["name"],
        "arguments_raw": call["arguments"],
        "arguments": parse_json(call["arguments"]),
        "started_at": started_at,
        "finished_at": finished_at,
        "duration_ms": elapsed_ms(started),
        "ok": _tool_ok(result),
        "result_raw": content,
        "result": parse_json(content),
    }


def _reuse_successful_result(
    call: dict[str, str],
    previous: dict[str, str],
) -> tuple[dict[str, str], dict[str, object]]:
    now = utc_now()
    result = {
        "role": "tool",
        "tool_call_id": call["id"],
        "content": previous["content"],
    }
    return result, {
        "id": call["id"],
        "name": call["name"],
        "arguments_raw": call["arguments"],
        "arguments": parse_json(call["arguments"]),
        "started_at": now,
        "finished_at": now,
        "duration_ms": 0.0,
        "ok": True,
        "reused": True,
        "result_raw": previous["content"],
        "result": parse_json(previous["content"]),
    }


def _call_signature(call: dict[str, str]) -> tuple[str, str]:
    raw_arguments = call["arguments"]
    try:
        arguments = json.loads(raw_arguments or "{}")
    except json.JSONDecodeError:
        canonical = raw_arguments
    else:
        canonical = json.dumps(
            arguments,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    return call["name"], canonical


def _record_chunk_metadata(response: dict[str, Any], metadata: dict[str, Any]) -> None:
    if not metadata:
        return

    standard = {
        "id",
        "object",
        "model",
        "created",
        "system_fingerprint",
        "usage",
        "timings",
    }
    for key in standard:
        if key in metadata:
            response[key] = metadata[key]

    provider = response["provider"]
    for key, value in metadata.items():
        if key in standard:
            continue
        if key == "prompt_progress":
            provider.setdefault("prompt_progress", []).append(value)
            continue
        provider[key] = value


def _validate_model_round(
    finish_reason: str | None,
    calls: list[dict[str, str]],
) -> None:
    if finish_reason == "tool_calls" and not calls:
        raise RuntimeError("model finished with tool_calls but returned no tool calls")

    if calls and finish_reason not in (None, "tool_calls"):
        logger.warning(
            "model returned tool calls with unexpected finish_reason=%s",
            finish_reason,
        )


def _validate_allowed_calls(
    calls: list[dict[str, str]],
    allowed_tool_names: set[str],
) -> None:
    for call in calls:
        if call["name"] not in allowed_tool_names:
            raise RuntimeError(f"model requested unknown tool: {call['name']}")


def _trim_context(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if len(messages) <= MAX_CONTEXT_MESSAGES:
        return messages

    start = len(messages) - MAX_CONTEXT_MESSAGES
    while start < len(messages) and messages[start].get("role") != "user":
        start += 1
    return messages[start:]


def _tool_ok(message: dict[str, str]) -> bool:
    try:
        body = json.loads(message["content"])
    except (KeyError, json.JSONDecodeError, TypeError):
        return False
    return bool(body.get("ok"))


def _assistant_message(
    content: str | None,
    calls: list[dict[str, str]],
) -> dict[str, Any]:
    message: dict[str, Any] = {
        "role": "assistant",
        "content": content,
    }
    if calls:
        message["tool_calls"] = [
            {
                "id": call["id"],
                "type": "function",
                "function": {
                    "name": call["name"],
                    "arguments": call["arguments"],
                },
            }
            for call in calls
        ]
    return message
