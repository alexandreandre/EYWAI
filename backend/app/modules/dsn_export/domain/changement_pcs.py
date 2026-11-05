"""Le bloc « Changements Contrat » (S21.G00.41) d'un code PCS-ESE changé.

Cahier technique DSN 2026.1.2 : les rubriques du bloc portent « la valeur avant changement »
(p. 215) ; la date de la modification est obligatoire, « du changement ou de la correction », et
la profondeur de recalcul l'est pour un bloc seul (p. 26) ; un bloc ne porte qu'une modalité
(p. 103). Guide OETH de l'Urssaf (v2.5, 7 avril 2026, p. 46) : ancien code en S21.G00.41.019,
profondeur « au premier jour du mois où le changement de caractéristique du contrat est
constaté », jamais avant le début du contrat (CCH-14) ni après la modification (CCH-15).

Le bloc part dans toute DSN du mois du changement (régénérée comprise), et dans celles des mois
suivants tant qu'aucune DSN d'un mois intermédiaire n'est partie. Un contrat commencé dans le
mois du changement n'a jamais été déclaré avec l'ancien code : pas de bloc. La DSN d'un mois
antérieur au changement déclare l'ancien code, en vigueur ce mois-là.
"""

from __future__ import annotations

from typing import AbstractSet, Any, Dict, Optional

from app.modules.dsn_export.domain.contract_map import debut_du_contrat
from app.modules.dsn_import.domain.model import ChangementContratBlock
from app.modules.pcs_ese.domain.changement import CLE, mois_du, valide


def _changement(classification: Any) -> Optional[Dict[str, Any]]:
    changement = classification.get(CLE) if isinstance(classification, dict) else None
    return changement if valide(changement) else None


def pcs_du_mois(classification: Any, pcs_actuel: str, period: str) -> str:
    """Le code en vigueur pendant le mois déclaré : l'ancien si le changement vient après."""
    changement = _changement(classification)
    if changement and mois_du(changement) > period[:7]:
        return str(changement["ancien"]).strip()
    return pcs_actuel


def bloc_changement_pcs(
    classification: Optional[Dict[str, Any]],
    pcs_actuel: str,
    period: str,
    periodes_declarees: AbstractSet[str],
    debut_contrat: str,
) -> Optional[ChangementContratBlock]:
    changement = _changement(classification)
    if not changement:
        return None
    ancien = str(changement["ancien"]).strip()
    jour = str(changement["date"])[:10]
    mois_changement = jour[:7]
    if not ancien or ancien == str(pcs_actuel or "").strip() or mois_changement > period[:7]:
        return None
    if any(mois_changement <= p < period[:7] for p in periodes_declarees):
        return None
    if not debut_contrat or str(debut_contrat)[:10] >= f"{mois_changement}-01":
        return None
    annee, mois, j = jour.split("-")
    date_dsn = f"{j}{mois}{annee}"
    return ChangementContratBlock(
        date_modification=date_dsn,
        rubriques={
            "S21.G00.41.001": date_dsn,
            "S21.G00.41.019": ancien,
            "S21.G00.41.028": f"01{mois}{annee}",
        },
    )


def avis_changements_pcs(
    employees_data: Any, period: str, periodes_declarees: AbstractSet[str]
) -> Optional[str]:
    """La ligne de l'aperçu DSN qui dit combien de changements de code partent ce mois-ci."""
    n = 0
    for row in employees_data or []:
        employee = (row.get("employee") or row) if isinstance(row, dict) else {}
        classification = employee.get("classification_conventionnelle")
        pcs = (classification or {}).get("pcs") if isinstance(classification, dict) else ""
        actuel = str(pcs or employee.get("pcs") or "")
        if bloc_changement_pcs(
            classification, actuel, period, periodes_declarees, debut_du_contrat(employee)
        ):
            n += 1
    if not n:
        return None
    return (
        f"Code PCS-ESE changé pour {n} salarié{'s' if n > 1 else ''} : la DSN déclare "
        "l'ancien code (bloc Changements Contrat, S21.G00.41)."
    )
