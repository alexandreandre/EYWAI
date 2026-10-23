"""Ce qui empêche de valider un bulletin, et ce qui dit qu'il est à régénérer.

Un bulletin dont le recalcul a échoué après une correction ne reflète plus ses
variables du mois ; un bulletin dont le mois précédent a changé depuis son
calcul porte des cumuls qui ne se suivent plus (audit du 28/09). Dans les deux
cas, le valider enverrait au salarié un bulletin faux.
"""

from __future__ import annotations

from typing import Any

from app.modules.payroll.domain.empreinte_entrees import (  # noqa: F401 — réexportés
    MESSAGE_A_RECALCULER,
    MESSAGE_A_REGENERER,
)
from app.modules.payroll.engine.corrections_manuelles import CLE_CORRECTIONS_EN_ATTENTE

_TOLERANCE = 0.011

MESSAGE_RECALCUL_EN_ATTENTE = (
    "Le bulletin n'a pas été recalculé après la dernière correction : "
    "régénérez-le avant de le valider."
)

MESSAGE_CORRECTION_EN_ATTENTE = (
    "Une correction faite à la main ne trouve plus sa ligne : retirez-la ou "
    "reportez-la sur une autre ligne (onglet « Corriger ») avant de valider."
)


#: Un brouillon recalculé au bac à sable, le verdict pas encore là (lot 43) : la
#: validation attend quelques secondes, au lieu de valider un bulletin peut-être faux.
MESSAGE_VERIFICATION_EN_COURS = (
    "Martine vérifie encore ce bulletin : le planning a changé depuis son calcul, et "
    "elle le recalcule sans rien enregistrer pour savoir si un montant change. "
    "Réessayez dans quelques secondes."
)


def raisons_de_ne_pas_valider(
    payslip_data: dict[str, Any] | None,
    raison_a_recalculer: str | None = None,
    *,
    verification_en_cours: bool = False,
) -> list[str]:
    """Recalcul en attente, entrées changées depuis le calcul (`raison_a_recalculer`,
    la phrase qui dit quoi — None quand rien n'a changé ou qu'on ne sait pas), ou
    vérification au bac à sable en cours."""
    raisons: list[str] = []
    if isinstance(payslip_data, dict) and payslip_data.get("recalcul_en_attente"):
        raisons.append(MESSAGE_RECALCUL_EN_ATTENTE)
    if isinstance(payslip_data, dict) and payslip_data.get(CLE_CORRECTIONS_EN_ATTENTE):
        raisons.append(MESSAGE_CORRECTION_EN_ATTENTE)
    if raison_a_recalculer:
        raisons.append(raison_a_recalculer)
    if verification_en_cours:
        raisons.append(MESSAGE_VERIFICATION_EN_COURS)
    return raisons


def _nombre(valeur: Any) -> float | None:
    if isinstance(valeur, bool):
        return None
    try:
        return float(valeur)
    except (TypeError, ValueError):
        return None


def cumul_brut(payslip_data: dict[str, Any] | None) -> float | None:
    """Le brut cumulé de l'année à la fin du mois, tel que le bulletin l'imprime."""
    bloc = (payslip_data or {}).get("cumuls") if isinstance(payslip_data, dict) else None
    if not isinstance(bloc, dict):
        return None
    interieur = bloc.get("cumuls") if isinstance(bloc.get("cumuls"), dict) else bloc
    return _nombre(interieur.get("brut_total"))


def a_regenerer(
    payslip_data: dict[str, Any] | None, cumul_brut_du_mois_precedent: float | None
) -> str | None:
    """La phrase à afficher quand les cumuls ne suivent plus le mois précédent.

    Le brut cumulé d'un mois moins son brut redonne le brut cumulé du mois
    d'avant ; si ce n'est plus le cas, le mois d'avant a été recalculé ou repris
    depuis. Rien à dire quand un des chiffres manque.
    """
    cumul = cumul_brut(payslip_data)
    brut = _nombre((payslip_data or {}).get("salaire_brut")) if isinstance(payslip_data, dict) else None
    if cumul is None or brut is None or cumul_brut_du_mois_precedent is None:
        return None
    if abs((cumul - brut) - cumul_brut_du_mois_precedent) > _TOLERANCE:
        return MESSAGE_A_REGENERER
    return None
