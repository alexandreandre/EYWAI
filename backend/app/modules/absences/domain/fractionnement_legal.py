"""Fractionnement CP — méthode légale depuis absences validées."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.modules.absences.domain.fractionnement import (
    FractionnementMbcResult,
    compute_fractionnement_days_mbc,
    FractionnementMbcInput,
)

LEGAL_MAIN_LEAVE_DAYS = 24
LEGAL_CONSECUTIVE_MIN = 12
LEGAL_PERIOD_START = (5, 1)   # 1er mai
LEGAL_PERIOD_END = (10, 31)   # 31 octobre


@dataclass(frozen=True)
class FractionnementLegalInput:
    validated_requests: list[dict]
    grant_year: int
    main_leave_days: float = LEGAL_MAIN_LEAVE_DAYS
    fifth_week_deduction_ouvres: float = 5.0
    ouvres_to_ouvrables_ratio: float = 1.2


def _parse_day(s: str) -> date | None:
    try:
        return date.fromisoformat(s[:10])
    except (TypeError, ValueError):
        return None


def _conge_paye_days_in_range(
    validated_requests: list[dict],
    start: date,
    end: date,
) -> list[date]:
    days: list[date] = []
    for req in validated_requests:
        if req.get("type") != "conge_paye" or req.get("status") != "validated":
            continue
        for d in req.get("selected_days") or []:
            parsed = _parse_day(d) if isinstance(d, str) else None
            if parsed and start <= parsed <= end:
                days.append(parsed)
    return sorted(set(days))


def _max_consecutive_working_days(dates: list[date]) -> int:
    if not dates:
        return 0
    best = 1
    current = 1
    for i in range(1, len(dates)):
        if (dates[i] - dates[i - 1]).days == 1:
            current += 1
            best = max(best, current)
        else:
            current = 1
    return best


def compute_fractionnement_legal(inp: FractionnementLegalInput) -> FractionnementMbcResult:
    """
    Calcule le reliquat du congé principal au 31/10 et applique les seuils légaux.
    Simplification : jours CP pris mai–oct. sur le congé principal (plafonné 24 j.).
    """
    period_start = date(inp.grant_year, *LEGAL_PERIOD_START)
    period_end = date(inp.grant_year, *LEGAL_PERIOD_END)

    taken_days = _conge_paye_days_in_range(
        inp.validated_requests, period_start, period_end
    )
    taken_count = float(len(taken_days))
    main_taken = min(taken_count, inp.main_leave_days)
    remaining_main = max(0.0, inp.main_leave_days - main_taken)

    max_consec = _max_consecutive_working_days(taken_days)
    if max_consec >= LEGAL_CONSECUTIVE_MIN:
        # 12 j. consécutifs pris : pas de fractionnement
        remaining_main = 0.0

    # Convertir reliquat principal (ouvrables) en ouvrés pour formule seuils
    ratio = inp.ouvres_to_ouvrables_ratio or 1.2
    remaining_ouvres = round(remaining_main / ratio, 2)

    return compute_fractionnement_days_mbc(
        FractionnementMbcInput(
            solde_cp_n1_ouvres=remaining_ouvres + inp.fifth_week_deduction_ouvres,
            cp_reported_june_ouvres=0.0,
            cp_seniority_deduction_ouvres=0.0,
            fifth_week_deduction_ouvres=inp.fifth_week_deduction_ouvres,
            ouvres_to_ouvrables_ratio=ratio,
        )
    )
