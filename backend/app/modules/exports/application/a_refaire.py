"""Quels exports déjà faits sont à refaire : la règle du domaine, avec ses deux lectures.

Lu par l'historique de l'écran Exports et par le bandeau « Déjà exporté » du
bulletin. Rien n'est lu quand aucun export ne dépend des bulletins.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from app.modules.exports.domain.a_refaire import (
    derniere_modification_par_mois,
    derniers_exports_tires_des_bulletins,
    exports_a_refaire,
    instant,
)
from app.modules.exports.infrastructure import queries as infra_queries


def ids_des_exports_a_refaire(company_id: str, exports: Iterable[Mapping[str, Any]]) -> set[str]:
    """Ids des exports (lignes `exports_history`) dont un bulletin du mois a changé depuis."""
    exports = list(exports)
    candidats = derniers_exports_tires_des_bulletins(exports)
    if not candidats:
        return set()
    annees = sorted({int(str(e["period"])[:4]) for e in candidats if str(e.get("period") or "")[:4].isdigit()})
    plus_ancien = min(candidats, key=lambda e: instant(e.get("generated_at")))
    modifies_le = derniere_modification_par_mois(
        infra_queries.list_calculs_des_bulletins(company_id, annees),
        infra_queries.list_suppressions_de_bulletins(company_id, str(plus_ancien["generated_at"])),
    )
    return exports_a_refaire(exports, modifies_le)
