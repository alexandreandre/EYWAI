"""
Ports (interfaces) pour le module rates.

L'infrastructure implémente ces interfaces ; l'application ne dépend que des abstractions.
Lecture seule : récupération des lignes brutes (groupement/formatage en application).
"""
from __future__ import annotations

from typing import Any, Protocol


class IAllRatesReader(Protocol):
    """
    Lecture des configurations de taux actives (table payroll_config).

    Retourne les lignes brutes (is_active=True). Le groupement par config_key
    et le formatage sont effectués dans la couche application.
    """

    def get_all_active_rows(self) -> list[dict[str, Any]]:
        """
        Toutes les lignes actives (is_active=True) de payroll_config.
        Chaque dict contient au moins : config_key, config_data, version,
        last_checked_at, created_at, comment, source_links.
        """
        ...
