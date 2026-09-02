from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from app.agent.router import route_for_intent
from app.domain.routing import Intent


@dataclass(frozen=True)
class IntentCase:
    case_id: str
    message: str
    intent: Intent
    route: str
    language: str
    family: str
    critical: bool = False
    active_workflow: str | None = None


def load_intent_cases(path: Path) -> list[IntentCase]:
    cases: list[IntentCase] = []
    seen_ids: set[str] = set()
    for line_number, raw in enumerate(
        path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        line = raw.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
            intent = Intent(payload["intent"])
            case = IntentCase(
                case_id=str(payload["id"]),
                message=str(payload["message"]).strip(),
                intent=intent,
                route=str(payload["route"]),
                language=str(payload["language"]),
                family=str(payload["family"]),
                critical=bool(payload.get("critical", False)),
                active_workflow=payload.get("active_workflow"),
            )
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"invalid intent case at {path}:{line_number}: {exc}") from exc

        if not case.case_id or case.case_id in seen_ids:
            raise ValueError(f"duplicate or empty case id at {path}:{line_number}")
        if not case.message:
            raise ValueError(f"empty message at {path}:{line_number}")
        if case.language not in {"es", "en"}:
            raise ValueError(f"unsupported language at {path}:{line_number}")
        if not case.family:
            raise ValueError(f"empty family at {path}:{line_number}")
        if route_for_intent(intent).value != case.route:
            raise ValueError(
                f"intent/route mismatch at {path}:{line_number}: "
                f"{intent.value} -> {route_for_intent(intent).value}, got {case.route}"
            )
        if case.active_workflow not in {None, "scheduling"}:
            raise ValueError(f"unsupported active_workflow at {path}:{line_number}")

        seen_ids.add(case.case_id)
        cases.append(case)
    return cases


def dataset_families(path: Path) -> set[str]:
    return {case.family for case in load_intent_cases(path)}
