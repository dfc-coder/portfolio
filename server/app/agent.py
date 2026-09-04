from __future__ import annotations

from collections.abc import AsyncIterator

from .llm import GenerationConfig, LlamaCpp
from .profile import Profile, profile_name
from .prompt import build_messages
from .search import PortfolioSearch
from .sessions import MemorySessions, Message


class PortfolioAgent:
    def __init__(
        self,
        profile: Profile,
        sessions: MemorySessions,
        search: PortfolioSearch,
        llm: LlamaCpp,
        config: GenerationConfig,
    ) -> None:
        self._subject = profile_name(profile)
        self._sessions = sessions
        self._search = search
        self._llm = llm
        self._config = config

    async def warm(self) -> None:
        await self._search.warm()

    async def respond(self, session_id: str, user_message: str) -> AsyncIterator[str]:
        async with self._sessions.open(session_id) as session:
            session.turns.append(Message(role="user", content=user_message))
            query = "\n".join(
                turn.content for turn in session.turns if turn.role == "user"
            )[-2000:]
            evidence = await self._search.search(query)
            messages = build_messages(self._subject, session.turns[-4:], evidence)

            response: list[str] = []
            async for chunk in self._llm.stream(messages, self._config):
                response.append(chunk)
                yield chunk

            if not response:
                raise RuntimeError("LLM returned an empty response")
            session.turns.append(Message(role="assistant", content="".join(response)))
