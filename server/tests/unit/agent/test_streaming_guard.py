import pytest

from app.agent.stream_guard import StreamGuard, UnsafeStreamOutput


def test_stream_guard_preserves_safe_text() -> None:
    guard = StreamGuard(holdback_chars=24)
    chunks = ["Diego trabaja ", "con Python, ", "FastAPI y AWS."]

    emitted = [guard.feed(chunk) for chunk in chunks]
    emitted.append(guard.finish())

    assert "".join(emitted) == "".join(chunks)


def test_stream_guard_blocks_completed_calendar_claim_across_chunks() -> None:
    guard = StreamGuard()
    emitted: list[str] = []

    emitted.append(guard.feed("Puedo explicarte el proceso. La reunión quedó agen"))
    with pytest.raises(UnsafeStreamOutput) as error:
        guard.feed("dada para mañana.")

    assert error.value.reason == "unverified_calendar_status"
    assert "agendada" not in "".join(emitted).lower()


def test_stream_guard_allows_capability_description() -> None:
    guard = StreamGuard()
    text = "Puedo agendar una reunión después de que confirmes explícitamente."
    assert guard.feed(text) + guard.finish() == text


def test_stream_guard_allows_owner_identity_disclaimer() -> None:
    guard = StreamGuard()
    text = "Hola. No soy Diego; soy su representante conversacional."
    assert guard.feed(text) + guard.finish() == text


def test_stream_guard_allows_english_owner_identity_disclaimer() -> None:
    guard = StreamGuard()
    text = "I'm not Diego; I'm his conversational representative."
    assert guard.feed(text) + guard.finish() == text


def test_stream_guard_blocks_owner_impersonation() -> None:
    guard = StreamGuard()

    with pytest.raises(UnsafeStreamOutput) as error:
        guard.feed("Hola, soy Diego y puedo ayudarte.")

    assert error.value.reason == "owner_impersonation"
