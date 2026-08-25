from __future__ import annotations

from app.infrastructure.config.settings import Settings


def test_pockettrace_is_disabled_by_default(monkeypatch) -> None:
    monkeypatch.delenv("POCKETTRACE_ENABLED", raising=False)

    settings = Settings.from_env()

    assert settings.pockettrace_enabled is False


def test_pockettrace_can_be_enabled_explicitly(monkeypatch) -> None:
    monkeypatch.setenv("POCKETTRACE_ENABLED", "true")

    settings = Settings.from_env()

    assert settings.pockettrace_enabled is True
