"""Ce que la DSN de Martine ne sait pas déclarer : dit, jamais silencieux.

Cahier technique NEODeS 2026.1.2 (dans le dépôt, docs/audit-maji-2026/sources) :
- S21.G00.65.001 : 501 congé divers non rémunéré, 607 présence parentale, 632
  congé parental d'éducation, 636 enfant malade, 650 proche aidant ;
- S21.G00.40.036 et 037 : emplois et employeurs multiples ;
- § 2.1.3.6 : les rappels survenant après la rupture suivent les mêmes principes,
  « les périodes de paie afférentes devront toutefois être bornées sur la date de
  fin de contrat de travail ».
Le solde annuel d'avril (CTP 995) est lu dans les DSN de l'ancien logiciel.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.modules.dsn_export.domain.evenements import (
    MOTIF_CONGE_NON_REMUNERE,
    suspensions_du_bulletin,
)

GENRE_REGULARISATION_PARTICIPATION = "regularisation_participation"

AVERTISSEMENT_EMPLOYEURS_MULTIPLES = (
    "Plusieurs employeurs : Martine déclare toujours un emploi et un employeur uniques "
    "(40.036 et 40.037 = 01) et ne calcule pas de plafond réparti. Pour un salarié à "
    "plusieurs employeurs, corrigez son bulletin et sa DSN à la main avant dépôt."
)


def avertissements_du_bulletin(payslip_data: Dict[str, Any], nir: str) -> List[str]:
    """Ce que ce bulletin déclare sans que Martine sache le déclarer exactement."""
    alertes: List[str] = []
    if any(motif == MOTIF_CONGE_NON_REMUNERE for motif, _, _ in suspensions_du_bulletin(payslip_data)):
        alertes.append(
            f"Congé sans solde déclaré 501 (NIR {nir or '?'}) : s'il s'agit d'un congé parental "
            "(632), d'une présence parentale (607), d'un proche aidant (650) ou d'un enfant "
            "malade (636), Martine ne sait pas le déclarer : corrigez le motif avant dépôt."
        )
    if payslip_data.get("bulletin_kind") == GENRE_REGULARISATION_PARTICIPATION:
        alertes.append(
            f"Participation versée à un ancien salarié (NIR {nir or '?'}) : la DSN la rattache "
            "à son contrat terminé, périodes bornées sur la date de fin (cahier technique, "
            "§ 2.1.3.6), jamais un contrat d'un jour. Martine ne borne pas encore ces "
            "périodes : vérifiez-les avant dépôt."
        )
    return alertes


def avertissement_cotisations_hors_bulletin(period: str) -> Optional[str]:
    """Avril : le solde annuel Urssaf (CTP 995) ne vient d'aucun bulletin."""
    if str(period)[5:7] != "04":
        return None
    return (
        "Cotisations Urssaf hors bulletin : le solde annuel d'avril (CTP 995) et toute "
        "réduction ponctuelle ne sont pas au bordereau, Martine ne sait pas les saisir. "
        "Ajoutez-les avant dépôt."
    )
