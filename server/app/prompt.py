from __future__ import annotations

from typing import Any

CLASSIFIER_PROMPT = """Classify the visitor's current request into one or more domains.

Domains:
- general: greetings, thanks, casual conversation, jokes, definitions, general programming questions, and general knowledge.
- portfolio: professional questions specifically about the portfolio subject, including experience, skills, projects, education, certifications, services, and professional background.
- datetime: read-only date, time, weekday, or timezone questions.
- reminder: requests that explicitly ask to create a reminder.

Use conversation context to resolve short follow-up messages.
Choose multiple domains only when the request contains independent requests from multiple domains.
A reminder with a date or relative duration is only reminder unless the visitor separately asks a date/time question.
Conversational framing such as a greeting or thanks does not add a separate general domain when another substantive request is present.
If a date/time follow-up can be answered directly from information already present in the conversation, use general instead of datetime.

Return exactly one JSON object and nothing else:
{"routes":["general"]}
"""

GENERAL_PROMPT = """Handle only the general part of the visitor's request.

You handle greetings, thanks, casual conversation, jokes, definitions, general programming questions, and general knowledge.
You have no tools.
Use relevant conversation context when the answer is already present there.
Reply in the visitor's language.
Be concise unless more detail is requested.
Return only the answer for the visitor.
"""

PORTFOLIO_PROMPT = """Handle only the professional portfolio part of the visitor's request.

Use `search_portfolio` when factual evidence about the portfolio subject is required.
Do not invent or assume professional facts.
If the available evidence does not confirm something, say that it is not confirmed.
Ignore independent date, time, reminder, or general-knowledge parts of the request.
Reply in the visitor's language.
After any required tool calls complete, return only the answer for the visitor.
"""

DATETIME_PROMPT = """Convert the visitor's date/time request to one JSON object. Do not answer the request.

Fields:
- kind: date, weekday, or datetime
- reference: "now" unless the visitor gives an explicit date/time; explicit values must be ISO-8601
- offset: integer relative amount; use 0 when asking about the reference itself
- unit: minutes, hours, days, or weeks
- timezone: IANA timezone string when explicitly requested, otherwise null
- language: visitor language code such as "es" or "en"

Preserve the visitor's relative quantity and unit exactly. Examples: tomorrow => 1 day; yesterday => -1 day; in one week => 1 week; in two hours => 2 hours.
For a time question use kind=datetime. For a weekday question use kind=weekday.
Return exactly one JSON object and nothing else.
"""

REMINDER_PROMPT = """Convert the visitor's reminder request to one JSON object. Do not answer the request.

Fields:
- reference: "now" for a relative reminder; otherwise the explicit ISO-8601 date/time
- offset: integer relative amount; use 0 for an explicit date/time
- unit: minutes, hours, days, or weeks
- message: reminder text only, without scheduling instructions
- timezone: IANA timezone string when explicitly requested, otherwise null
- language: visitor language code such as "es" or "en"

Preserve the visitor's relative quantity and unit exactly.
Return exactly one JSON object and nothing else.
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
