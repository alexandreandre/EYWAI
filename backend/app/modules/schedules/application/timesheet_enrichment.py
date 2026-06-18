"""
Enrichissement métier post-extraction des relevés de pointage.

Fériés observés, week-end, plafond heures journalières.
"""

from __future__ import annotations

from datetime import date
from typing import List

from app.modules.schedules.schemas.ai import AiDayEntry, AiEmployeeProposal
from app.shared.public_holidays import day_numbers_observed_holidays

MAX_HOURS_PER_DAY = 12.0


def _is_weekend(year: int, month: int, jour: int) -> bool:
    try:
        wd = date(year, month, jour).weekday()
        return wd >= 5
    except ValueError:
        return False


def enrich_employee_days(
    proposal: AiEmployeeProposal,
    *,
    year: int,
    month: int,
    company_id: str | None,
    max_hours_per_day: float = MAX_HOURS_PER_DAY,
) -> AiEmployeeProposal:
    """Applique les règles RH sur les jours d'un employé."""
    holiday_days = day_numbers_observed_holidays(year, month, company_id)
    enriched: List[AiDayEntry] = []

    for day in proposal.days:
        jour = day.jour
        heures = day.heures
        day_type = day.type

        if jour in holiday_days:
            if heures is not None and heures > 0:
                proposal.warnings.append(
                    f"Jour {jour} : {heures:.2f} h sur un jour férié — "
                    "à confirmer (travail possible)."
                )
            else:
                day_type = "ferie"
                heures = None
        elif _is_weekend(year, month, jour):
            if heures is None or heures <= 0:
                if day_type in ("absence", "travail"):
                    day_type = "weekend"
                    heures = None

        if heures is not None and heures > max_hours_per_day:
            proposal.warnings.append(
                f"Jour {jour} : {heures:.2f} h dépasse le plafond "
                f"({max_hours_per_day:.0f} h) — vérifiez l'OCR."
            )

        enriched.append(
            AiDayEntry(
                jour=jour,
                heures=heures,
                type=day_type,
                nature=day.nature,
            )
        )

    proposal.days = enriched
    return proposal


def enrich_proposal_employees(
    employees: List[AiEmployeeProposal],
    *,
    year: int,
    month: int,
    company_id: str | None,
) -> List[AiEmployeeProposal]:
    return [
        enrich_employee_days(emp, year=year, month=month, company_id=company_id)
        for emp in employees
    ]


__all__ = [
    "MAX_HOURS_PER_DAY",
    "enrich_employee_days",
    "enrich_proposal_employees",
]
