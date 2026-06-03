"""
Requêtes applicatives (read) pour rates.

Délèguent au reader (lignes brutes) puis au service (groupement + formatage).
Aucune logique métier lourde ici : orchestration uniquement.
"""

from __future__ import annotations

from typing import Any

from app.modules.rates.application.service import group_payroll_configs_by_key
from app.modules.rates.domain.interfaces import IAllRatesReader
from app.modules.rates.infrastructure.official_sources import merge_official_urls_into_rates


def get_all_rates(
    reader: IAllRatesReader,
) -> dict[str, dict[str, Any]]:
    """
    Récupère toutes les configurations actives de taux, groupées par config_key.

    Lit les lignes brutes via le reader, applique le groupement et le formatage
    (service) puis retourne le dict de sortie. Comportement identique au legacy.
    """
    rows = reader.get_all_active_rows()
    grouped = group_payroll_configs_by_key(rows)
    return merge_official_urls_into_rates(grouped)
