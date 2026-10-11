"""Préavis : exécuté, ou non exécuté avec ou sans indemnité compensatrice.

Code du travail, art. L1234-5 (Légifrance, version en vigueur depuis le
01/05/2008, ouvert le 11/10/2026) : « Lorsque le salarié n'exécute pas le
préavis, il a droit, sauf s'il a commis une faute grave, à une indemnité
compensatrice. L'inexécution du préavis, notamment en cas de dispense par
l'employeur, n'entraîne aucune diminution des salaires et avantages que le
salarié aurait perçus s'il avait accompli son travail jusqu'à l'expiration du
préavis, indemnité de congés payés comprise. »

service-public.gouv.fr F2883, « Démission d'un salarié » (vérifié le
08/07/2026, ouvert le 11/10/2026) : dispense « À sa demande et après
acceptation de l'employeur […] l'indemnité compensatrice de préavis n'est pas
due. Ou à la seule initiative de l'employeur. Celui-ci doit néanmoins verser
l'indemnité compensatrice de préavis. »

Une valeur par cas (colonne `employee_exits.notice_indemnity_type`), lue de la
même façon par l'écran, le calcul et les documents de sortie :
- « executed » : préavis exécuté, payé avec le salaire du mois ; aucune indemnité ;
- « paid » : dispense à l'initiative de l'employeur ; indemnité compensatrice
  (valeur historique, gardée : « payée » voulait dire « indemnité versée ») ;
- « waived » : dispense à la demande du salarié, acceptée ; rien n'est dû ;
- « not_applicable » : pas de préavis.

Module pur : aucune lecture, aucune écriture.
"""

from __future__ import annotations

from datetime import date
from typing import Optional

PREAVIS_EXECUTE = "executed"
DISPENSE_PAR_L_EMPLOYEUR = "paid"
DISPENSE_A_LA_DEMANDE_DU_SALARIE = "waived"
SANS_PREAVIS = "not_applicable"

TYPES_DE_PREAVIS = (
    PREAVIS_EXECUTE,
    DISPENSE_PAR_L_EMPLOYEUR,
    DISPENSE_A_LA_DEMANDE_DU_SALARIE,
    SANS_PREAVIS,
)

#: Un mois de préavis compte 30 jours, comme la durée proposée à l'écran
#: (employee_exits.domain.notice_period.MONTH_CALENDAR_DAYS).
JOURS_PAR_MOIS = 30

_PHRASES = {
    PREAVIS_EXECUTE: "Préavis exécuté, payé avec le salaire.",
    DISPENSE_PAR_L_EMPLOYEUR: (
        "Préavis non exécuté, dispense à l'initiative de l'employeur : "
        "indemnité compensatrice de préavis versée."
    ),
    DISPENSE_A_LA_DEMANDE_DU_SALARIE: (
        "Préavis non exécuté à la demande du salarié, dispense acceptée : "
        "pas d'indemnité compensatrice."
    ),
}


def indemnite_compensatrice_due(type_preavis: Optional[str], *, faute_grave: bool = False) -> bool:
    """Seule la dispense à l'initiative de l'employeur ouvre l'indemnité (L1234-5)."""
    return type_preavis == DISPENSE_PAR_L_EMPLOYEUR and not faute_grave


def phrase_execution_preavis(type_preavis: Optional[str]) -> str:
    """La phrase que portent le reçu, le certificat et l'attestation France Travail."""
    return _PHRASES.get(str(type_preavis or ""), "Aucun préavis applicable.")


def jours_de_preavis_restants(
    *,
    jours_de_preavis: int,
    fin_du_preavis: Optional[date],
    dernier_jour_travaille: Optional[date],
) -> int:
    """Le temps de préavis que le salarié ne fait pas : du lendemain du dernier
    jour travaillé à la fin du préavis, jamais plus que la durée du préavis.
    Sans date de fin connue, toute la durée."""
    jours = max(0, int(jours_de_preavis or 0))
    if fin_du_preavis is None or dernier_jour_travaille is None:
        return jours
    return max(0, min(jours, (fin_du_preavis - dernier_jour_travaille).days))
