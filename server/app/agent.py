from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import AsyncIterator
from typing import Any

from openai import AsyncOpenAI

from .portfolio import Portfolio
from .prompt import build_messages
from .tool_search import ToolSearch, all_tools, tool_name
from .tools import run_tool_call
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
        tool_search: ToolSearch | None = None,
        prefetch_portfolio: bool = False,
        temperature: float = 0.7,
        top_p: float = 0.8,
        top_k: int = 20,
        min_p: float = 0.0,
        presence_penalty: float = 1.5,
        repeat_penalty: float = 1.0,
        max_tokens: int = 256,
    ) -> None:
        self._subject = subject
        self._chat = chat
        self._portfolio = portfolio
        self._model = model
        self._tool_search = tool_search
        self._prefetch_portfolio = prefetch_portfolio
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
        portfolio_evidence: list[dict[str, str]] = []
        if self._prefetch_portfolio:
            portfolio_evidence = await self._portfolio.search(message)
            selection = all_tools()
            eligible_tools = [
                tool
                for tool in selection.tools
                if tool_name(tool) != "search_portfolio"
            ]
        else:
            selection = (
                await self._tool_search.select(message, context)
                if self._tool_search is not None
                else all_tools()
            )
            eligible_tools = selection.tools

        allowed_tool_names = {tool_name(tool) for tool in eligible_tools}
        messages = build_messages(
            self._subject,
            _trim_context(context),
            message,
        )
        if portfolio_evidence:
            evidence = json.dumps(
                portfolio_evidence,
                ensure_ascii=False,
                separators=(",", ":"),
            )
            messages[0]["content"] += (
                "\n\n<portfolio_evidence>\n"
                f"{evidence}\n"
                "</portfolio_evidence>"
            )

        generation = {
            "temperature": self._temperature,
            "top_p": self._top_p,
            "top_k": self._top_k,
            "min_p": self._min_p,
            "presence_penalty": self._presence_penalty,
            "repeat_penalty": self._repeat_penalty,
            "max_tokens": self._max_tokens,
            "parallel_tool_calls": len(eligible_tools) > 1,
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        trace = TurnTrace(
            message=message,
            context=context,
            model=self._model,
            generation=generation,
            tools=eligible_tools,
        )
        if self._prefetch_portfolio:
            trace.data["tool_search"] = {
                "selected": [tool_name(tool) for tool in eligible_tools],
                "scores": {},
                "latency_ms": 0.0,
                "mode": "static",
            }
            trace.data["portfolio_retrieval"] = {
                "count": len(portfolio_evidence),
                "sources": [item.get("source", "") for item in portfolio_evidence],
            }
        else:
            trace.data["tool_search"] = selection.trace()

        successful_calls: dict[tuple[str, str], dict[str, str]] = {}
        force_answer = False

        try:
            round_number = 1
            while True:
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
                if eligible_tools and not force_answer:
                    request["tools"] = eligible_tools
                    request["parallel_tool_calls"] = len(eligible_tools) > 1

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
                            yield "status", {"phase": "responding", "round": round_number}
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

                repeated_results = _reused_successful_results(ordered_calls, successful_calls)
                if repeated_results is not None:
                    round_trace["tool_calls"] = [item[1] for item in repeated_results]
                    messages.extend(item[0] for item in repeated_results)
                    force_answer = True
                    round_number += 1
                    continue

                if round_number > MAX_TOOL_ROUNDS:
                    raise RuntimeError("tool loop limit reached")

                for call in ordered_calls:
                    yield "tool", {
                        "name": call["name"],
                        "state": "running",
                        "round": round_number,
                    }

                executed = await asyncio.gather(
                    *(
                        _run_traced_tool(call, self._portfolio)
                        for call in ordered_calls
                    )
                )
                results = [result for result, _ in executed]
                round_trace["tool_calls"] = [tool_trace for _, tool_trace in executed]

                for call, result in zip(ordered_calls, results, strict=True):
                    yield "tool", {
                        "name": call["name"],
                        "state": "done",
                        "ok": _tool_ok(result),
                        "round": round_number,
                    }
                    if _tool_ok(result):
                        successful_calls[_call_signature(call)] = result

                messages.extend(results)
                round_number += 1
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


def _reused_successful_results(
    calls: list[dict[str, str]],
    successful_calls: dict[tuple[str, str], dict[str, str]],
) -> list[tuple[dict[str, str], dict[str, object]]] | None:
    if not calls:
        return None

    signatures = [_call_signature(call) for call in calls]
    if not all(signature in successful_calls for signature in signatures):
        return None

    reused: list[tuple[dict[str, str], dict[str, object]]] = []
    now = utc_now()
    for call, signature in zip(calls, signatures, strict=True):
        previous = successful_calls[signature]
        result = {
            "role": "tool",
            "tool_call_id": call["id"],
            "content": previous["content"],
        }
        reused.append(
            (
                result,
                {
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
                },
            )
        )
    return reused


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

    for key in ("id", "object", "model", "created", "system_fingerprint", "usage", "timings"):
        if key in metadata:
            response[key] = metadata[key]

    provider = response["provider"]
    for key, value in metadata.items():
        if key in {"id", "object", "model", "created", "system_fingerprint", "usage", "timings"}:
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
            raise RuntimeError(f"model requested ineligible tool: {call['name']}")


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
