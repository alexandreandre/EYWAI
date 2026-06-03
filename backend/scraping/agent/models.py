"""Routing modèles OpenRouter pour l'agent de réparation."""

from __future__ import annotations

import os

# Réparation code (Moonshot Kimi K2.6 — dernier Kimi dispo sur OpenRouter)
MODEL_CODE_REPAIR = os.getenv(
    "EYWAI_REPAIR_MODEL_CODE", "moonshotai/kimi-k2.6"
)
# Retries : même modèle (déjà très compétitif en Q/P)
MODEL_CODE_REPAIR_RETRY = os.getenv(
    "EYWAI_REPAIR_MODEL_RETRY", "moonshotai/kimi-k2.6"
)
# Recherche URL officielle
MODEL_URL_SEARCH = os.getenv(
    "EYWAI_REPAIR_MODEL_URL", "perplexity/sonar"
)

MAX_ITERATIONS = int(os.getenv("EYWAI_REPAIR_MAX_ITERATIONS", "5"))
BUDGET_CAP_USD = float(os.getenv("EYWAI_REPAIR_BUDGET_CAP", "2.0"))

ENV_AGENT_DISABLED = "EYWAI_REPAIR_AGENT_DISABLED"

from core.official_domains import OFFICIAL_WEB_SEARCH_DOMAINS

# Rétrocompatibilité (agent, orchestrator, source_validator)
OFFICIAL_DOMAINS = list(OFFICIAL_WEB_SEARCH_DOMAINS)


def agent_disabled() -> bool:
    return os.environ.get(ENV_AGENT_DISABLED, "").strip() in ("1", "true", "yes")


def code_model_for_iteration(attempt: int) -> str:
    """Kimi K2.6 par défaut ; routing alterné si CODE et RETRY diffèrent (env)."""
    if MODEL_CODE_REPAIR == MODEL_CODE_REPAIR_RETRY:
        return MODEL_CODE_REPAIR
    if attempt in (1, 3):
        return MODEL_CODE_REPAIR
    return MODEL_CODE_REPAIR_RETRY
