"""Ce qui empêche de valider un bulletin, et ce qui dit qu'il est à régénérer.

Un bulletin dont le recalcul a échoué après une correction ne reflète plus ses
variables du mois ; un bulletin dont le mois précédent a changé depuis son
calcul porte des cumuls qui ne se suivent plus (audit du 28/09). Dans les deux
cas, le valider enverrait au salarié un bulletin faux.
"""

from __future__ import annotations

from typing import Any

_TOLERANCE = 0.011

MESSAGE_RECALCUL_EN_ATTENTE = (
    "Le bulletin n'a pas été recalculé après la dernière correction : "
    "régénérez-le avant de le valider."
)
MESSAGE_A_REGENERER = (
    "Le bulletin du mois précédent a changé depuis le calcul de celui-ci : "
    "leurs cumuls ne se suivent plus. Régénérez ce bulletin."
)


def raisons_de_ne_pas_valider(payslip_data: dict[str, Any] | None) -> list[str]:
    if isinstance(payslip_data, dict) and payslip_data.get("recalcul_en_attente"):
        return [MESSAGE_RECALCUL_EN_ATTENTE]
    return []


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
