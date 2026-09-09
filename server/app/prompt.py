from __future__ import annotations

from typing import Any

CLASSIFIER_PROMPT = """Classify the visitor's current request into one or more domains.

Domains:
- general: greetings, thanks, casual conversation, jokes, definitions, general programming questions, and general knowledge.
- portfolio: professional questions specifically about the portfolio subject, including experience, skills, projects, education, certifications, services, and professional background.
- temporal: date, time, weekday, timezone, and reminder requests.

Use conversation context to resolve short follow-up messages.
Choose multiple domains only when the request contains independent requests from multiple domains.
Conversational framing such as a greeting or thanks does not add a separate general domain when another substantive request is present.

Return exactly one JSON object and nothing else:
{"routes":["general"]}
"""

GENERAL_PROMPT = """Handle only the general part of the visitor's request.

You handle greetings, thanks, casual conversation, jokes, definitions, general programming questions, and general knowledge.
You have no tools.
Reply in the visitor's language.
Be concise unless more detail is requested.

Return exactly one JSON object and nothing else:
{"answer":"your answer"}
"""

PORTFOLIO_PROMPT = """Handle only the professional portfolio part of the visitor's request.

Use `search_portfolio` when factual evidence about the portfolio subject is required.
Do not invent or assume professional facts.
If the available evidence does not confirm something, say that it is not confirmed.
Ignore independent date, time, reminder, or general-knowledge parts of the request.
Reply in the visitor's language.

Return exactly one JSON object and nothing else after any required tool calls complete:
{"answer":"your answer"}
"""

TEMPORAL_PROMPT = """Handle only the date, time, timezone, weekday, or reminder part of the visitor's request.

Use `resolve_datetime` for date or time questions.
Use `set_reminder_mock` only when the visitor asks to create a reminder.
Preserve relative durations exactly in tool arguments. For example: tomorrow means offset=1 and unit=days; yesterday means offset=-1 and unit=days; in one week means offset=1 and unit=weeks; in two hours means offset=2 and unit=hours.
Ignore independent portfolio or general-knowledge parts of the request.
Reply in the visitor's language.

Return exactly one JSON object and nothing else after any required tool calls complete:
{"answer":"your answer"}
"""


def build_classifier_messages(
    subject: str,
    context: list[dict[str, Any]],
    message: str,
) -> list[dict[str, str]]:
    system = f"""{CLASSIFIER_PROMPT}

<portfolio_subject>
<name>{subject}</name>
</portfolio_subject>
"""
    return [
        {"role": "system", "content": system},
        *_classifier_context(context),
        {"role": "user", "content": message},
    ]


def build_worker_messages(
    subject: str,
    prompt: str,
    context: list[dict[str, Any]],
    message: str,
) -> list[dict[str, Any]]:
    system = f"""{prompt}

<portfolio_subject>
<name>{subject}</name>
</portfolio_subject>
"""
    return [
        {"role": "system", "content": system},
        *context,
        {"role": "user", "content": message},
    ]


def _classifier_context(context: list[dict[str, Any]]) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    for item in context:
        role = item.get("role")
        content = item.get("content")
        if role not in {"user", "assistant"} or not isinstance(content, str):
            continue
        if not content.strip():
            continue
        messages.append({"role": role, "content": content})
    return messages[-8:]
