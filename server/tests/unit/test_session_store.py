from __future__ import annotations

import asyncio

import pytest

from app.infrastructure.sessions.memory import MemorySessionStore


@pytest.mark.asyncio
async def test_same_session_turns_are_serialized() -> None:
    store = MemorySessionStore()
    first_entered = asyncio.Event()
    release_first = asyncio.Event()
    order: list[str] = []

    async def first() -> None:
        async with store.session("session-same"):
            order.append("first-start")
            first_entered.set()
            await release_first.wait()
            order.append("first-end")

    async def second() -> None:
        await first_entered.wait()
        async with store.session("session-same"):
            order.append("second")

    first_task = asyncio.create_task(first())
    second_task = asyncio.create_task(second())

    await first_entered.wait()
    await asyncio.sleep(0)
    assert order == ["first-start"]

    release_first.set()
    await asyncio.gather(first_task, second_task)

    assert order == ["first-start", "first-end", "second"]


@pytest.mark.asyncio
async def test_different_sessions_can_progress_concurrently() -> None:
    store = MemorySessionStore()
    first_entered = asyncio.Event()
    second_entered = asyncio.Event()
    release_first = asyncio.Event()

    async def first() -> None:
        async with store.session("session-one"):
            first_entered.set()
            await release_first.wait()

    async def second() -> None:
        await first_entered.wait()
        async with store.session("session-two"):
            second_entered.set()

    first_task = asyncio.create_task(first())
    second_task = asyncio.create_task(second())

    await first_entered.wait()
    await asyncio.wait_for(second_entered.wait(), timeout=1.0)
    release_first.set()
    await asyncio.gather(first_task, second_task)


@pytest.mark.asyncio
async def test_session_store_evicts_oldest_inactive_session_at_capacity() -> None:
    store = MemorySessionStore(max_sessions=2)
    first = await store.get("session-one")
    await asyncio.sleep(0.001)
    await store.get("session-two")
    await asyncio.sleep(0.001)
    await store.get("session-three")

    recreated = await store.get("session-one")

    assert recreated is not first


@pytest.mark.asyncio
async def test_session_store_never_evicts_active_session() -> None:
    store = MemorySessionStore(max_sessions=1)

    async with store.session("session-active"):
        with pytest.raises(RuntimeError, match="Session capacity reached"):
            await store.get("session-other")

    replacement = await store.get("session-other")
    assert replacement.session_id == "session-other"
