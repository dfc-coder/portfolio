from __future__ import annotations

from typing import Any

CLASSIFIER_PROMPT = """Classify the visitor's current request into one or more domains.

Domains:
- general: greetings, thanks, casual conversation, jokes, definitions, general programming questions, general knowledge, and questions about the assistant's capabilities or behavior.
- portfolio: professional questions about the portfolio subject or a known portfolio project, including experience, skills, projects, technologies, implementation language, education, certifications, services, and professional background.
- datetime: read-only date, time, weekday, or timezone questions.
- reminder: requests that explicitly ask to create or schedule a reminder for an action.

Use conversation context to resolve short follow-up messages.
A question about a project listed in <portfolio_projects> is portfolio even when the portfolio subject's name is omitted.
Generic programming concepts such as REST, JSON, APIs, languages, or frameworks are general unless the visitor asks whether the portfolio subject or a listed project uses them.
Choose multiple domains only when the request contains independent requests from multiple domains.
Questions about whether reminders are real, persistent, supported, or how they work are general; they do not create a reminder.
A reminder with a date or relative duration is only reminder unless the visitor separately asks a date/time question.
Conversational framing such as a greeting or thanks does not add a separate general domain when another substantive request is present.
If a date/time follow-up can be answered directly from information already present in the conversation, use general instead of datetime.

Return exactly one JSON object and nothing else:
{"routes":["general"]}
"""

GENERAL_PROMPT = """Handle only the general part of the visitor's request.

You handle greetings, thanks, casual conversation, jokes, definitions, general programming questions, general knowledge, and questions about this assistant's capabilities or behavior.
You have no tools.
The available reminder feature is simulated and non-persistent; it does not send a real notification.
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

DATETIME_PROMPT = """Convert the visitor's date/time request to the structured contract. Do not answer the request.

Rules:
- kind: date, weekday, or datetime.
- reference: use "now" for current or relative requests. For an explicit date without a time use YYYY-MM-DD exactly. For an explicit date and time use ISO-8601.
- offset and unit: preserve the relative quantity and unit. Examples: tomorrow = 1 day; yesterday = -1 day; one week = 1 week; two hours = 2 hours. Use offset 0 only for the reference itself.
- timezone: include only when the visitor explicitly requests a timezone. Never infer one.
- language: visitor language code such as es or en.

For a time question use kind=datetime. For a weekday question use kind=weekday.
Return only the structured object.
"""

REMINDER_PROMPT = """Convert the visitor's reminder request to the structured contract. Do not answer the request.

Rules:
- reference: use "now" for every relative reminder. Never convert a relative reminder to an absolute date. For an explicit date or time use ISO-8601.
- offset and unit: preserve the relative quantity and unit exactly. Examples: 30 minutes = 30 minutes; 2 hours = 2 hours; 7 days = 7 days. Use offset 0 for an explicit date or time.
- message: reminder text only, without scheduling instructions.
- timezone: include only when the visitor explicitly requests a timezone. Never infer one.
- language: visitor language code such as es or en.

Return only the structured object.
"""


def build_classifier_messages(
    subject: str,
    context: list[dict[str, Any]],
    message: str,
    project_names: tuple[str, ...] = (),
) -> list[dict[str, str]]:
    projects = "\n".join(f"- {name}" for name in project_names)
    system = f"""{CLASSIFIER_PROMPT}

<portfolio_subject>
<name>{subject}</name>
</portfolio_subject>
<portfolio_projects>
{projects}
</portfolio_projects>
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
