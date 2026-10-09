"""Routing modèles OpenRouter pour l'agent de réparation."""

from __future__ import annotations

import os

from core.env_produit import lire_env

# Réparation code (Moonshot Kimi K2.6 — dernier Kimi dispo sur OpenRouter)
MODEL_CODE_REPAIR = lire_env(
    "MARTINE_REPAIR_MODEL_CODE", "moonshotai/kimi-k2.6"
)
# Retries : même modèle (déjà très compétitif en Q/P)
MODEL_CODE_REPAIR_RETRY = lire_env(
    "MARTINE_REPAIR_MODEL_RETRY", "moonshotai/kimi-k2.6"
)
# Recherche URL officielle
MODEL_URL_SEARCH = lire_env(
    "MARTINE_REPAIR_MODEL_URL", "perplexity/sonar"
)

MAX_ITERATIONS = int(lire_env("MARTINE_REPAIR_MAX_ITERATIONS", "5"))
BUDGET_CAP_USD = float(lire_env("MARTINE_REPAIR_BUDGET_CAP", "2.0"))

ENV_AGENT_ENABLED = "MARTINE_REPAIR_AGENT_ENABLED"
# Rétrocompat : explicit disable force l'arrêt même si ENABLED=1
ENV_AGENT_DISABLED = "MARTINE_REPAIR_AGENT_DISABLED"

from core.official_domains import OFFICIAL_WEB_SEARCH_DOMAINS

# Rétrocompatibilité (agent, orchestrator, source_validator)
OFFICIAL_DOMAINS = list(OFFICIAL_WEB_SEARCH_DOMAINS)


def agent_disabled() -> bool:
    if (lire_env(ENV_AGENT_DISABLED, "") or "").strip().lower() in ("1", "true", "yes"):
        return True
    return (lire_env(ENV_AGENT_ENABLED, "") or "").strip().lower() not in ("1", "true", "yes")


def code_model_for_iteration(attempt: int) -> str:
    """Kimi K2.6 par défaut ; routing alterné si CODE et RETRY diffèrent (env)."""
    if MODEL_CODE_REPAIR == MODEL_CODE_REPAIR_RETRY:
        return MODEL_CODE_REPAIR
    if attempt in (1, 3):
        return MODEL_CODE_REPAIR
    return MODEL_CODE_REPAIR_RETRY
