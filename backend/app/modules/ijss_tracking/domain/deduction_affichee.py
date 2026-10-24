"""La déduction d'IJSS d'un arrêt sans subrogation, telle que le suivi la montre.

Les clés viennent du maintien du bulletin actuel (`payroll/domain/ijss_deduites`).
Rien ici ne calcule : on lit ce que le moteur a posé.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping, Optional

from app.modules.payroll.domain.ijss_deduites import (
    CLE_IJSS_DEDUITES,
    CLE_SOURCE,
    montant_deduit,
)


def deduction_du_bulletin(payslip_data: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    """Montant déduit, source et jours maintenus ; tout à None sans déduction."""
    bloc = payslip_data.get("bloc_maintien") if isinstance(payslip_data, Mapping) else None
    maintien = bloc.get("maintien") if isinstance(bloc, Mapping) else None
    deduites = montant_deduit(maintien)
    if deduites <= 0 or not isinstance(maintien, Mapping):
        return {"ijss_deduites": None, "ijss_deduites_source": None, "nb_jours_maintenus": None}
    try:
        jours = int(maintien.get("nb_jours_maintien") or 0)
    except (TypeError, ValueError):
        jours = 0
    return {
        "ijss_deduites": deduites,
        "ijss_deduites_source": maintien.get(CLE_SOURCE),
        "nb_jours_maintenus": jours or None,
    }


def montant_applique_sans_effet(
    *,
    subrogation_active: bool,
    applique: bool,
    bulletin_connu: bool,
    deduction: Mapping[str, Any],
) -> bool:
    """Un montant appliqué qui ne change plus le bulletin.

    Arrêt non subrogé, montant déjà appliqué, bulletin actuel lu, et aucune
    déduction dessus : la société verse le garanti en entier.
    """
    return (
        bulletin_connu
        and applique
        and not subrogation_active
        and not deduction.get(CLE_IJSS_DEDUITES)
    )
