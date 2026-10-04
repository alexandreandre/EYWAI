"""
Règles métier transverses liées au statut d'emploi (sans I/O).
"""

from __future__ import annotations

import calendar
import copy
from collections.abc import Mapping
from datetime import date
from typing import Any


def _parse_employment_date(value: Any) -> date | None:
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return date.fromisoformat(value.strip()[:10])
        except ValueError:
            return None
    return None


def payslip_employment_period_block_reason(
    employee: Mapping[str, Any],
    year: int,
    month: int,
) -> str | None:
    """Motif de blocage si le mois ne chevauche pas la présence du salarié."""
    if month < 1 or month > 12:
        return f"Mois de paie invalide : {month}."

    start = _parse_employment_date(
        employee.get("date_debut_execution") or employee.get("hire_date")
    )
    if start is None:
        return (
            "Impossible de générer ce bulletin : la date d'entrée dans l'entreprise "
            "n'est pas renseignée."
        )

    period_start = date(year, month, 1)
    period_end = date(year, month, calendar.monthrange(year, month)[1])
    if period_end < start:
        return (
            f"Impossible de générer le bulletin de {month:02d}/{year} : "
            f"le collaborateur n'était pas encore présent dans l'entreprise "
            f"(entrée le {start.strftime('%d/%m/%Y')})."
        )

    end = _parse_employment_date(
        employee.get("exit_last_working_day") or employee.get("contract_end_date")
    )
    if end is not None and period_start > end:
        return (
            f"Impossible de générer le bulletin de {month:02d}/{year} : "
            f"le collaborateur n'était plus présent dans l'entreprise "
            f"(sortie le {end.strftime('%d/%m/%Y')})."
        )
    return None


def premier_mois_du_contrat(employee: Mapping[str, Any], year: int, month: int) -> bool:
    """Vrai si le contrat en cours commence dans ce mois.

    Même date de début que la garde de présence : le début d'exécution, à
    défaut la date d'entrée de la fiche. Après « Nouveau contrat », la fiche
    porte la date de début du nouveau contrat ; une suite en CDI garde celle
    du CDD (même contrat, L1243-11).
    """
    start = _parse_employment_date(
        employee.get("date_debut_execution") or employee.get("hire_date")
    )
    return start is not None and (start.year, start.month) == (year, month)


def mois_du_contrat_en_cours(employee: Mapping[str, Any], year: int, month: int) -> bool:
    """Faux pour un mois d'avant le début du contrat en cours (date inconnue : vrai).

    Ce mois appartient à un contrat terminé : son bulletin ne se recalcule plus
    (la garde de présence refuse un mois d'avant l'entrée de la fiche).
    """
    start = _parse_employment_date(
        employee.get("date_debut_execution") or employee.get("hire_date")
    )
    return start is None or (year, month) >= (start.year, start.month)


def cumuls_precedents_du_contrat(
    cumuls_precedents: dict | None,
    employee: Mapping[str, Any],
    year: int,
    month: int,
    depart_vide: dict,
) -> dict | None:
    """Les cumuls de départ du bulletin : ceux du mois d'avant, sauf au premier mois d'un contrat.

    La réduction générale se calcule pour chaque contrat (CSS L241-13, III ;
    D241-7, V ; BOSS § 1070), l'indemnité de fin de CDD sur le seul contrat
    (C. trav. L1243-8), et les congés du contrat précédent ont été payés à sa
    fin (L1242-16). Au premier mois d'un contrat, les cumuls du mois d'avant
    sont ceux d'un autre contrat, ou n'existent pas : on part de `depart_vide`,
    le zéro propre à chaque générateur.
    """
    if premier_mois_du_contrat(employee, year, month):
        return copy.deepcopy(depart_vide)
    return cumuls_precedents


def is_employee_present_for_payslip_month(
    employee: Mapping[str, Any],
    year: int,
    month: int,
) -> bool:
    """True si le salarié est présent au moins un jour du mois de paie."""
    return payslip_employment_period_block_reason(employee, year, month) is None


def is_forfait_jour(statut: str | None, explicit: bool | None = None) -> bool:
    """True si le salarié est géré en forfait jours.

    Le booléen explicite est la source de vérité. Le libellé historique reste
    supporté pour les anciennes données non encore migrées.
    """
    if explicit is not None:
        return bool(explicit)
    if not statut:
        return False
    return "forfait jour" in statut.lower()


def is_cadre(statut: str | None) -> bool:
    """Cadre / assimilé cadre (ex. « Cadre au forfait jour »), hors non-cadre."""
    compact = (statut or "").strip().lower().replace(" ", "").replace("-", "")
    return "cadre" in compact and "noncadre" not in compact


def is_non_cadre(statut: str | None) -> bool:
    compact = (statut or "").strip().lower().replace(" ", "").replace("-", "")
    return "noncadre" in compact


def statut_categoriel_clean(statut: str | None) -> str | None:
    """Retourne le statut catégoriel sans pollution forfait jours."""
    if is_cadre(statut):
        return "Cadre"
    if is_non_cadre(statut):
        return "Non-Cadre"
    return statut


def effective_statut_for_payroll(
    statut: str | None, explicit_forfait_jour: bool | None = None
) -> str | None:
    """Libellé interne rétrocompatible pour les modules encore basés sur statut."""
    clean = statut_categoriel_clean(statut)
    if is_forfait_jour(statut, explicit_forfait_jour):
        base = clean or "Cadre"
        if "forfait jour" in base.lower():
            return base
        return f"{base} au forfait jour"
    return clean


__all__ = [
    "cumuls_precedents_du_contrat",
    "effective_statut_for_payroll",
    "is_cadre",
    "is_employee_present_for_payslip_month",
    "is_forfait_jour",
    "is_non_cadre",
    "payslip_employment_period_block_reason",
    "premier_mois_du_contrat",
    "statut_categoriel_clean",
]
