import pytest

from app.agent.streaming_guard import StreamingOutputGuard, UnsafeStreamOutput


def test_streaming_guard_preserves_safe_text() -> None:
    guard = StreamingOutputGuard(holdback_chars=16)
    chunks = ["Diego trabaja ", "con Python, ", "FastAPI y AWS."]

    emitted = [guard.feed(chunk) for chunk in chunks]
    emitted.append(guard.finish())

    assert "".join(emitted) == "".join(chunks)


def test_streaming_guard_blocks_calendar_claim_across_chunks_before_commit() -> None:
    guard = StreamingOutputGuard()
    emitted: list[str] = []

    emitted.append(guard.feed("Puedo explicarte el proceso. La reunión quedó agen"))
    with pytest.raises(UnsafeStreamOutput) as error:
        guard.feed("dada para mañana.")

    assert error.value.reason == "unverified_calendar_status"
    assert "agendada" not in "".join(emitted).lower()


def test_streaming_guard_blocks_owner_impersonation() -> None:
    guard = StreamingOutputGuard()

    with pytest.raises(UnsafeStreamOutput) as error:
        guard.feed("Hola, soy Diego y puedo ayudarte.")

    assert error.value.reason == "owner_impersonation"
