"""Client OpenRouter async : résolution de modèle, transmission kwargs, journalisation."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


def _fake_response(total_tokens: int = 42):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content='{"ok": true}'))],
        usage=SimpleNamespace(total_tokens=total_tokens),
    )


def test_create_async_resolves_alias_and_forwards_kwargs(monkeypatch):
    from app.shared.infrastructure.ai import client_async

    fake_client = MagicMock()
    fake_client.chat.completions.create = AsyncMock(return_value=_fake_response())
    monkeypatch.setattr(client_async, "get_async_chat_client", lambda: fake_client)

    result = asyncio.run(
        client_async.chat_completions_create_async(
            model="gpt-4o-mini", temperature=0.0, timeout=60.0
        )
    )

    assert result.usage.total_tokens == 42
    kwargs = fake_client.chat.completions.create.call_args.kwargs
    assert kwargs["model"] == "openai/gpt-4o-mini"
    assert kwargs["timeout"] == 60.0
    assert kwargs["temperature"] == 0.0


def test_create_async_logs_and_reraises_on_failure(monkeypatch):
    from app.shared.infrastructure.ai import client_async

    fake_client = MagicMock()
    fake_client.chat.completions.create = AsyncMock(side_effect=RuntimeError("boom"))
    monkeypatch.setattr(client_async, "get_async_chat_client", lambda: fake_client)

    with patch.object(client_async.logger, "warning") as mock_warning:
        with pytest.raises(RuntimeError):
            asyncio.run(
                client_async.chat_completions_create_async(model="google/gemini-2.5-flash")
            )
    logged = " ".join(str(a) for a in mock_warning.call_args.args)
    assert "gemini-2.5-flash" in logged
