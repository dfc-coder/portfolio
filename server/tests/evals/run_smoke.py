from __future__ import annotations

import asyncio
import json
from pathlib import Path

import httpx

import run_live
import run_scheduling_turn_live as scheduling_eval
from app.infrastructure.config.settings import Settings
from app.infrastructure.embeddings.llama_cpp import LlamaCppEmbeddingClient
from app.infrastructure.llm.llama_cpp import LlamaCppClient


ROUTING_CASE_IDS = {
    "b03",
    "b09",
    "s01",
    "s12",
    "c01",
    "i02",
    "g02",
}
CONVERSATION_CASE_IDS = {
    "conv01",
    "conv05",
}
SCHEDULING_CASE_IDS = {
    "st01",
    "st06",
    "st14",
    "st22",
    "st27",
    "st38",
}


def selected(cases: list[dict], ids: set[str]) -> list[dict]:
    return [case for case in cases if case.get("id") in ids]


async def main() -> int:
    settings = Settings.from_env()
    eval_dir = Path(__file__).resolve().parent
    live_cases = run_live.load_cases(eval_dir / "cases.jsonl")
    scheduling_cases = scheduling_eval.load_cases(eval_dir / "scheduling_turn_cases.jsonl")

    routing_cases = selected(live_cases, ROUTING_CASE_IDS)
    conversation_cases = selected(live_cases, CONVERSATION_CASE_IDS)
    turn_cases = selected(scheduling_cases, SCHEDULING_CASE_IDS)

    print("[smoke] checking live model services...", flush=True)

    async with (
        httpx.AsyncClient(timeout=settings.llama_timeout_seconds) as llm_http,
        httpx.AsyncClient(timeout=settings.embedding_timeout_seconds) as embedding_http,
    ):
        llm = LlamaCppClient(
            settings.llama_base_url,
            settings.llama_model,
            settings.llama_timeout_seconds,
            client=llm_http,
        )
        embeddings = LlamaCppEmbeddingClient(
            settings.embedding_base_url,
            settings.embedding_model,
            settings.embedding_timeout_seconds,
            client=embedding_http,
        )

        llm_ready = await llm.health()
        embedding_ready = await embeddings.health()
        print(
            f"[smoke] llama={'ready' if llm_ready else 'DOWN'} "
            f"embedding={'ready' if embedding_ready else 'DOWN'}",
            flush=True,
        )
        if not llm_ready or not embedding_ready:
            return 2

        router = run_live.build_router(embeddings)
        routing_passed = 0
        print(f"[smoke] routing: {len(routing_cases)} cases", flush=True)
        for index, case in enumerate(routing_cases, start=1):
            result = await run_live.evaluate_routing([case], router, 1)
            passed = result["accuracy"] == 1.0
            routing_passed += int(passed)
            print(
                f"  [{index}/{len(routing_cases)}] {case['id']}: "
                f"{'PASS' if passed else 'FAIL'}",
                flush=True,
            )

        conversation_passed = 0
        print(f"[smoke] conversations: {len(conversation_cases)} cases", flush=True)
        for index, case in enumerate(conversation_cases, start=1):
            result = await run_live.evaluate_conversations(
                [case],
                settings,
                llm,
                embeddings,
                1,
            )
            passed = (
                result["pass_rate"] == 1.0
                and result["unexpected_calendar_writes"] == 0
            )
            conversation_passed += int(passed)
            print(
                f"  [{index}/{len(conversation_cases)}] {case['id']}: "
                f"{'PASS' if passed else 'FAIL'}",
                flush=True,
            )
            if not passed and result["failures"]:
                print(
                    "    " + json.dumps(result["failures"][0], ensure_ascii=False),
                    flush=True,
                )

        recording_llm = scheduling_eval.RecordingLlm(llm)
        scheduling_passed = 0
        print(f"[smoke] scheduling parser: {len(turn_cases)} cases", flush=True)
        for index, case in enumerate(turn_cases, start=1):
            result = await scheduling_eval.evaluate(
                [case],
                settings,
                recording_llm,
                1,
            )
            passed = result["semantic_accuracy"] == 1.0
            scheduling_passed += int(passed)
            print(
                f"  [{index}/{len(turn_cases)}] {case['id']}: "
                f"{'PASS' if passed else 'FAIL'}",
                flush=True,
            )
            if not passed and result["failures"]:
                print(
                    "    " + json.dumps(result["failures"][0], ensure_ascii=False),
                    flush=True,
                )

    summary = {
        "routing": f"{routing_passed}/{len(routing_cases)}",
        "conversations": f"{conversation_passed}/{len(conversation_cases)}",
        "scheduling": f"{scheduling_passed}/{len(turn_cases)}",
    }
    print("[smoke] " + json.dumps(summary, ensure_ascii=False), flush=True)

    all_passed = (
        routing_passed == len(routing_cases)
        and conversation_passed == len(conversation_cases)
        and scheduling_passed == len(turn_cases)
    )
    return 0 if all_passed else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
