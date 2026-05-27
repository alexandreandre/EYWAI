"""
Client OpenRouter (API compatible OpenAI) pour tous les appels LLM de l'application.
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

from openai import OpenAI

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Alias courts → identifiants OpenRouter (usage interne)
_MODEL_ALIASES: dict[str, str] = {
    "gpt-4o-mini": "openai/gpt-4o-mini",
    "gpt-4o": "openai/gpt-4o",
    "gpt-4": "openai/gpt-4",
}


def get_llm_api_key() -> str | None:
    """Clé API OpenRouter (obligatoire pour les appels IA en production)."""
    key = (os.getenv("OPENROUTER_API_KEY") or "").strip()
    return key or None


def is_llm_configured() -> bool:
    return bool(get_llm_api_key())


def require_llm_api_key() -> str:
    key = get_llm_api_key()
    if not key:
        raise ValueError(
            "OPENROUTER_API_KEY non définie. Configurez une clé OpenRouter pour activer l'IA."
        )
    return key


def resolve_model(model: str) -> str:
    """Normalise un identifiant de modèle (alias court ou id OpenRouter)."""
    stripped = model.strip()
    if "/" in stripped:
        return stripped
    return _MODEL_ALIASES.get(stripped, stripped)


@lru_cache(maxsize=1)
def get_chat_client() -> OpenAI:
    return OpenAI(
        base_url=OPENROUTER_BASE_URL,
        api_key=require_llm_api_key(),
        default_headers={
            "HTTP-Referer": os.getenv("OPENROUTER_HTTP_REFERER", "https://eywai.app"),
            "X-Title": os.getenv("OPENROUTER_APP_TITLE", "EYWAI"),
        },
    )


def chat_completions_create(*, model: str, **kwargs: Any) -> Any:
    """Appel chat.completions.create via OpenRouter (modèle obligatoire)."""
    client = get_chat_client()
    return client.chat.completions.create(model=resolve_model(model), **kwargs)
