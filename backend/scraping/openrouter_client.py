"""
Client OpenRouter pour les scripts de scraping (hors package app).

Modèles définis dans le code, pas dans .env.
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

from openai import OpenAI

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Modèle scraping (aligné sur app.shared.infrastructure.ai.models.MODEL_SCRAPING_EXTRACTION)
MODEL_SCRAPING_EXTRACTION = "openai/gpt-4o-mini"

# Modèle avec recherche web native (Perplexity Sonar) — tous les scripts *_AI.py
MODEL_WEB_SEARCH = "perplexity/sonar"

# Variante premium (recherche plus profonde, meilleure fraîcheur) — sources
# tabulaires exigeantes type barème kilométrique où sonar de base renvoie des
# valeurs périmées. Plus coûteux : à réserver aux scrapers qui le justifient.
MODEL_WEB_SEARCH_PRO = "perplexity/sonar-pro"

# Agent de réparation scraping (code / URL)
MODEL_CODE_REPAIR = "moonshotai/kimi-k2.6"
MODEL_CODE_REPAIR_RETRY = "moonshotai/kimi-k2.6"
MODEL_URL_SEARCH = MODEL_WEB_SEARCH

_MODEL_ALIASES: dict[str, str] = {
    "gpt-4o-mini": MODEL_SCRAPING_EXTRACTION,
    "kimi-k2.6": MODEL_CODE_REPAIR,
    "kimi-k2.5": "moonshotai/kimi-k2.5",
    "sonar": MODEL_WEB_SEARCH,
    "sonar-pro": MODEL_WEB_SEARCH_PRO,
}


def get_api_key() -> str | None:
    return (os.getenv("OPENROUTER_API_KEY") or "").strip() or None


def require_api_key() -> str:
    key = get_api_key()
    if not key:
        raise ValueError("OPENROUTER_API_KEY manquante.")
    return key


def resolve_model(model: str) -> str:
    stripped = model.strip()
    if "/" in stripped:
        return stripped
    return _MODEL_ALIASES.get(stripped, stripped)


@lru_cache(maxsize=1)
def get_client() -> OpenAI:
    return OpenAI(
        base_url=OPENROUTER_BASE_URL,
        api_key=require_api_key(),
        default_headers={
            "HTTP-Referer": os.getenv("OPENROUTER_HTTP_REFERER", "https://eywai.app"),
            "X-Title": os.getenv("OPENROUTER_APP_TITLE", "EYWAI Scraping"),
        },
    )


def chat_completions_create(
    *, model: str = MODEL_SCRAPING_EXTRACTION, **kwargs: Any
) -> Any:
    client = get_client()
    return client.chat.completions.create(model=resolve_model(model), **kwargs)
