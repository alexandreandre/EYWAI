"""Le bloc « Changements Contrat » (S21.G00.41) d'un code PCS-ESE changé.

Cahier technique DSN 2026.1.2 : les rubriques du bloc portent « la valeur avant changement »
(p. 215) ; la date de la modification est obligatoire, « du changement ou de la correction », et
la profondeur de recalcul l'est pour un bloc seul (p. 26) ; un bloc ne porte qu'une modalité
(p. 103). Guide OETH de l'Urssaf (v2.5, 7 avril 2026, p. 46) : ancien code en S21.G00.41.019,
profondeur « au premier jour du mois où le changement de caractéristique du contrat est
constaté ». Le bloc part dans chaque DSN tant qu'aucune DSN du mois du changement, ou d'un mois
suivant, n'est partie.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from app.modules.dsn_import.domain.model import ChangementContratBlock
from app.modules.pcs_ese.domain.changement import CLE, en_attente


def bloc_changement_pcs(
    classification: Optional[Dict[str, Any]],
    pcs_actuel: str,
    period: str,
    derniere_periode_deposee: Optional[str],
) -> Optional[ChangementContratBlock]:
    changement = classification.get(CLE) if isinstance(classification, dict) else None
    if not en_attente(changement, derniere_periode_deposee):
        return None
    ancien = str(changement["ancien"]).strip()
    jour = str(changement["date"])[:10]
    if not ancien or ancien == str(pcs_actuel or "").strip() or jour[:7] > period[:7]:
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
    employees_data: Any, period: str, derniere_periode_deposee: Optional[str]
) -> Optional[str]:
    """La ligne de l'aperçu DSN qui dit combien de changements de code partent ce mois-ci."""
    n = 0
    for row in employees_data or []:
        employee = (row.get("employee") or row) if isinstance(row, dict) else {}
        classification = employee.get("classification_conventionnelle")
        pcs = (classification or {}).get("pcs") if isinstance(classification, dict) else ""
        if bloc_changement_pcs(classification, str(pcs or employee.get("pcs") or ""), period, derniere_periode_deposee):
            n += 1
    if not n:
        return None
    return (
        f"Code PCS-ESE changé pour {n} salarié{'s' if n > 1 else ''} : la DSN déclare "
        "l'ancien code (bloc Changements Contrat, S21.G00.41)."
    )
