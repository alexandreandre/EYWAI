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


class IRatesWriter(Protocol):
    """
    Écriture manuelle versionnée d'une configuration de taux (table payroll_config).

    Préserve l'invariant « une seule ligne is_active par config_key + historique
    immuable versionné » : désactive la version courante et insère une nouvelle
    version. Aucune réécriture en place des taux actifs.
    """

    def get_active_config(self, config_key: str) -> dict[str, Any] | None:
        """Ligne active (is_active=True) pour un config_key, ou None."""
        ...

    def save_manual_version(
        self,
        *,
        config_key: str,
        new_config_data: dict[str, Any],
        comment: str,
        source_links: list[str],
    ) -> dict[str, Any]:
        """
        Versionne un bloc config_data complet (saisie manuelle).

        Retourne un dict de résultat : config_key, version (nouvelle), changed (bool),
        et id de la ligne active résultante.
        """
        ...
