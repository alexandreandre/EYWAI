"""Client OpenRouter async : timeouts explicites, retries SDK, journalisation par appel."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

import httpx
from openai import AsyncOpenAI

from app.shared.infrastructure.ai.client import (
    OPENROUTER_BASE_URL,
    require_llm_api_key,
    resolve_model,
)

logger = logging.getLogger("app.ai")

# Lecture longue (PDF multi-pages) mais bornée — le défaut SDK est de 600 s.
_DEFAULT_TIMEOUT = httpx.Timeout(connect=10.0, read=120.0, write=30.0, pool=10.0)

# Un AsyncOpenAI (et son pool httpx) est lié à la boucle asyncio qui l'a créé.
# Chaque job tourne dans son propre asyncio.run() : un cache global unique
# (lru_cache) réutiliserait un client d'une boucle déjà fermée d'un job à
# l'autre (transports qui fuient, comportement dépendant de la version).
# On cache donc par boucle courante et on ferme explicitement en fin de job.
_clients_by_loop: dict[int, AsyncOpenAI] = {}


def get_async_chat_client() -> AsyncOpenAI:
    import os

    loop = asyncio.get_running_loop()
    client = _clients_by_loop.get(id(loop))
    if client is None:
        client = AsyncOpenAI(
            base_url=OPENROUTER_BASE_URL,
            api_key=require_llm_api_key(),
            timeout=_DEFAULT_TIMEOUT,
            max_retries=2,  # backoff SDK sur 429/5xx
            default_headers={
                "HTTP-Referer": os.getenv("OPENROUTER_HTTP_REFERER", "https://eywai.app"),
                "X-Title": os.getenv("OPENROUTER_APP_TITLE", "EYWAI"),
            },
        )
        _clients_by_loop[id(loop)] = client
    return client


async def aclose_current_loop_client() -> None:
    """Ferme et oublie le client de la boucle courante (fin d'un job)."""
    client = _clients_by_loop.pop(id(asyncio.get_running_loop()), None)
    if client is not None:
        await client.close()


async def chat_completions_create_async(*, model: str, **kwargs: Any) -> Any:
    """chat.completions.create async via OpenRouter, avec trace durée/tokens."""
    resolved = resolve_model(model)
    started = time.monotonic()
    try:
        response = await get_async_chat_client().chat.completions.create(
            model=resolved, **kwargs
        )
    except Exception as exc:
        logger.warning(
            "Appel IA échoué model=%s durée=%dms erreur=%s",
            resolved,
            int((time.monotonic() - started) * 1000),
            exc,
        )
        raise
    usage = getattr(response, "usage", None)
    logger.info(
        "Appel IA model=%s durée=%dms tokens=%s",
        resolved,
        int((time.monotonic() - started) * 1000),
        getattr(usage, "total_tokens", None),
    )
    return response
