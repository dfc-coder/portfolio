from __future__ import annotations

import time
from collections.abc import AsyncIterator
from typing import Any
from uuid import uuid4

from openai import AsyncOpenAI

from .dispatcher import Dispatch, Route, classify
from .portfolio import Portfolio
from .prompt import GENERAL_PROMPT, PORTFOLIO_PROMPT
from .temporal import run_datetime_fast_path, run_reminder_fast_path
from .tools import SEARCH_PORTFOLIO_SCHEMA
from .trace import elapsed_ms, utc_now
from .worker import Worker, WorkerResult, run_worker

MAX_CONTEXT_MESSAGES = 32
AgentEvent = tuple[str, dict[str, object]]


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
        self._workers = {
            Route.GENERAL: Worker(
                route=Route.GENERAL,
                prompt=GENERAL_PROMPT,
                tools=(),
            ),
            Route.PORTFOLIO: Worker(
                route=Route.PORTFOLIO,
                prompt=PORTFOLIO_PROMPT,
                tools=(SEARCH_PORTFOLIO_SCHEMA,),
            ),
        }

    async def respond(
        self,
        message: str,
        context: list[dict[str, Any]],
        *,
        diagnostics: bool = False,
    ) -> AsyncIterator[AgentEvent]:
        started = time.perf_counter()
        trace_id = str(uuid4())
        started_at = utc_now()
        dispatch: Dispatch | None = None
        results: list[WorkerResult] = []
        trimmed_context = _trim_context(context)

        try:
            yield "status", {"phase": "dispatch"}
            dispatch = await classify(
                self._chat,
                model=self._model,
                subject=self._subject,
                message=message,
                context=trimmed_context,
            )
            yield "status", {
                "phase": "dispatched",
                "routes": [route.value for route in dispatch.routes],
            }

            for route in dispatch.routes:
                if route == Route.DATETIME:
                    result = await self._run_datetime(
                        message,
                        trimmed_context,
                        diagnostics=diagnostics,
                    )
                    results.append(result)
                    continue

                if route == Route.REMINDER:
                    result = await self._run_reminder(
                        message,
                        trimmed_context,
                        diagnostics=diagnostics,
                    )
                    results.append(result)
                    continue

                worker = self._workers[route]
                result: WorkerResult | None = None

                async for event, payload in run_worker(
                    self._subject,
                    self._chat,
                    self._portfolio,
                    worker,
                    message,
                    trimmed_context,
                    model=self._model,
                    temperature=self._temperature,
                    top_p=self._top_p,
                    top_k=self._top_k,
                    min_p=self._min_p,
                    presence_penalty=self._presence_penalty,
                    repeat_penalty=self._repeat_penalty,
                    max_tokens=self._max_tokens,
                    diagnostics=diagnostics,
                ):
                    if event == "result":
                        value = payload.get("value") if isinstance(payload, dict) else None
                        if not isinstance(value, WorkerResult):
                            raise RuntimeError("worker returned an invalid result")
                        result = value
                        continue
                    if event == "trace":
                        continue
                    if isinstance(payload, dict):
                        yield event, payload

                if result is None:
                    raise RuntimeError(f"worker returned no result: {route.value}")
                results.append(result)

            answer = _compose(results)
            returned_context = _build_context(trimmed_context, message, results, answer)

            yield "status", {"phase": "responding"}
            yield "token", {"text": answer}
            yield "context", {"messages": returned_context}

            if diagnostics:
                yield "trace", _build_trace(
                    trace_id=trace_id,
                    started_at=started_at,
                    started=started,
                    message=message,
                    context=context,
                    dispatch=dispatch,
                    results=results,
                    output=answer,
                    returned_context=returned_context,
                    error=None,
                )
            return
        except Exception as exc:
            if diagnostics:
                yield "trace", _build_trace(
                    trace_id=trace_id,
                    started_at=started_at,
                    started=started,
                    message=message,
                    context=context,
                    dispatch=dispatch,
                    results=results,
                    output=None,
                    returned_context=None,
                    error={"type": type(exc).__name__, "message": str(exc)},
                )
            raise

    async def _run_datetime(
        self,
        message: str,
        context: list[dict[str, Any]],
        *,
        diagnostics: bool,
    ) -> WorkerResult:
        return await run_datetime_fast_path(
            self._chat,
            model=self._model,
            message=message,
            context=context,
            temperature=self._temperature,
            top_p=self._top_p,
            top_k=self._top_k,
            min_p=self._min_p,
            presence_penalty=self._presence_penalty,
            repeat_penalty=self._repeat_penalty,
            max_tokens=self._max_tokens,
            diagnostics=diagnostics,
        )

    async def _run_reminder(
        self,
        message: str,
        context: list[dict[str, Any]],
        *,
        diagnostics: bool,
    ) -> WorkerResult:
        return await run_reminder_fast_path(
            self._chat,
            model=self._model,
            message=message,
            context=context,
            temperature=self._temperature,
            top_p=self._top_p,
            top_k=self._top_k,
            min_p=self._min_p,
            presence_penalty=self._presence_penalty,
            repeat_penalty=self._repeat_penalty,
            max_tokens=self._max_tokens,
            diagnostics=diagnostics,
        )


def _compose(results: list[WorkerResult]) -> str:
    if not results:
        raise RuntimeError("no worker results to compose")
    return "\n\n".join(result.answer for result in results if result.answer).strip()


def _build_context(
    context: list[dict[str, Any]],
    message: str,
    results: list[WorkerResult],
    answer: str,
) -> list[dict[str, Any]]:
    messages = [*context, {"role": "user", "content": message}]
    for result in results:
        messages.extend(result.protocol_messages)
    messages.append({"role": "assistant", "content": answer})
    return _trim_context(messages)


def _build_trace(
    *,
    trace_id: str,
    started_at: str,
    started: float,
    message: str,
    context: list[dict[str, Any]],
    dispatch: Dispatch | None,
    results: list[WorkerResult],
    output: str | None,
    returned_context: list[dict[str, Any]] | None,
    error: dict[str, str] | None,
) -> dict[str, Any]:
    workers = [result.trace for result in results]
    rounds = [
        round_trace
        for worker_trace in workers
        for round_trace in worker_trace.get("rounds", [])
    ]
    return {
        "trace_id": trace_id,
        "started_at": started_at,
        "finished_at": utc_now(),
        "duration_ms": elapsed_ms(started),
        "status": "error" if error else "ok",
        "input": {"message": message, "context": context},
        "model": {"name": workers[0].get("model", {}).get("name") if workers else None},
        "dispatch": {
            "routes": [route.value for route in dispatch.routes] if dispatch else [],
            "raw": dispatch.raw if dispatch else None,
        },
        "workers": workers,
        "rounds": rounds,
        "output": output,
        "returned_context": returned_context,
        "error": error,
    }


def _trim_context(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if len(messages) <= MAX_CONTEXT_MESSAGES:
        return messages

    start = len(messages) - MAX_CONTEXT_MESSAGES
    while start < len(messages) and messages[start].get("role") != "user":
        start += 1
    return messages[start:]
