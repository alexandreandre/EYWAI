"""Ce que l'écran demande : la liste des codes et la proposition pour un salarié."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict, List, Optional, Sequence

from app.modules.pcs_ese.domain.proposition import (
    FicheCollegue,
    Proposition,
    collegues_de,
    proposer,
)
from app.modules.pcs_ese.domain.referentiel import charger_referentiel


def proposition_pour(
    company_id: str,
    poste: str,
    statut: str,
    employee_id: Optional[str] = None,
    fiches: Optional[Sequence[FicheCollegue]] = None,
) -> Proposition:
    if fiches is None:
        from app.modules.pcs_ese.infrastructure.fiches import fiches_du_groupe

        fiches = fiches_du_groupe(company_id)
    societe, groupe = collegues_de(
        fiches, company_id=company_id, poste=poste, statut=statut, exclure_id=employee_id
    )
    return proposer(
        poste=poste, statut=statut, collegues_societe=societe, collegues_groupe=groupe
    )


def proposition_en_dict(proposition: Proposition) -> Dict[str, Any]:
    return asdict(proposition)


def referentiel_pour_ecran() -> List[Dict[str, Any]]:
    """Les 430 codes dans l'ordre de la table DSN (« 9999 » en dernier), avec leurs métiers."""
    return [
        {
            "code": r.code,
            "libelle": r.libelle,
            "metiers": list(r.typiques) + list(r.assimilees),
            "ecap": r.ecap,
            "public": r.public,
        }
        for r in charger_referentiel().values()
    ]
