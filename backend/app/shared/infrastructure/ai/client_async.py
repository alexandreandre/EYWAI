"""Client OpenRouter async : timeouts explicites, retries SDK, journalisation par appel."""

from __future__ import annotations

import logging
import time
from functools import lru_cache
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


@lru_cache(maxsize=1)
def get_async_chat_client() -> AsyncOpenAI:
    import os

    return AsyncOpenAI(
        base_url=OPENROUTER_BASE_URL,
        api_key=require_llm_api_key(),
        timeout=_DEFAULT_TIMEOUT,
        max_retries=2,  # backoff SDK sur 429/5xx
        default_headers={
            "HTTP-Referer": os.getenv("OPENROUTER_HTTP_REFERER", "https://eywai.app"),
            "X-Title": os.getenv("OPENROUTER_APP_TITLE", "EYWAI"),
        },
    )


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
