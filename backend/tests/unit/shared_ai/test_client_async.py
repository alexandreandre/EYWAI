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


def test_get_async_chat_client_is_scoped_per_event_loop(monkeypatch):
    """Un asyncio.run() suivant d'un autre ne doit pas réutiliser le transport
    httpx d'une boucle déjà fermée (fuite de transports entre jobs)."""
    from app.shared.infrastructure.ai import client_async

    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
    client_async._clients_by_loop.clear()

    made_clients = []

    def _fake_async_openai(**kwargs):
        client = MagicMock()
        client.close = AsyncMock()
        made_clients.append(client)
        return client

    monkeypatch.setattr(client_async, "AsyncOpenAI", _fake_async_openai)

    first = asyncio.run(_call_and_return(client_async))
    second = asyncio.run(_call_and_return(client_async))

    assert first is not second
    assert len(made_clients) == 2
    assert client_async._clients_by_loop == {}


async def _call_and_return(client_async):
    client = client_async.get_async_chat_client()
    await client_async.aclose_current_loop_client()
    return client


def test_aclose_current_loop_client_is_noop_when_nothing_cached():
    from app.shared.infrastructure.ai import client_async

    client_async._clients_by_loop.clear()
    asyncio.run(client_async.aclose_current_loop_client())
