"""
Mappers infrastructure rates : ligne DB → forme de sortie API.

Délègue au domain pour la définition du contrat de sortie (clés exposées).
"""
from __future__ import annotations

from typing import Any

from app.modules.rates.domain.rules import build_rate_category_output


def rate_config_row_to_output(row: dict[str, Any]) -> dict[str, Any]:
    """
    Transforme une ligne payroll_config (après sélection) en dict de sortie API.

    Contrat défini en domain (build_rate_category_output). Comportement identique au legacy.
    """
    return build_rate_category_output(row)
