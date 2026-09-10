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
