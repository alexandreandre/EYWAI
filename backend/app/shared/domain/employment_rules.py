"""
Règles métier transverses liées au statut d'emploi (sans I/O).
"""

from __future__ import annotations

import calendar
from datetime import date
from typing import Any, Mapping


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
    "is_forfait_jour",
    "is_cadre",
    "is_non_cadre",
    "statut_categoriel_clean",
    "effective_statut_for_payroll",
    "is_employee_present_for_payslip_month",
    "payslip_employment_period_block_reason",
]
