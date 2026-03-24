"""
Service applicatif rates : orchestration entre reader, domain et sortie.

Délègue au domain pour les règles métier (sélection, format). Aucun accès DB direct.
"""
from __future__ import annotations

import logging
from typing import Any

from app.modules.rates.domain.rules import (
    build_rate_category_output,
    group_and_select_best,
)


def group_payroll_configs_by_key(
    rows: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """
    Regroupe les lignes payroll_config par config_key et formate la sortie.

    Règles métier (domain) : priorité version puis created_at ; forme de sortie (domain).
    Comportement strictement identique au legacy.
    """
    grouped = group_and_select_best(rows)
    result = {
        k: build_rate_category_output(row)
        for k, row in grouped.items()
    }
    logging.info("✅ %s catégories de taux retournées : %s", len(result), list(result.keys()))
    return result
