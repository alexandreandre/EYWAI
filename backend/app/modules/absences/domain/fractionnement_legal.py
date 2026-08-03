"""Fractionnement CP — méthode légale depuis absences validées."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.modules.absences.domain.fractionnement import (
    FractionnementMbcResult,
    compute_fractionnement_days_mbc,
    FractionnementMbcInput,
)

# Congé principal : 24 jours ouvrables, soit 20 jours ouvrés.
LEGAL_MAIN_LEAVE_OUVRABLES = 24
LEGAL_MAIN_LEAVE_OUVRES = 20
LEGAL_PERIOD_START = (5, 1)   # 1er mai
LEGAL_PERIOD_END = (10, 31)   # 31 octobre


@dataclass(frozen=True)
class FractionnementLegalInput:
    validated_requests: list[dict]
    grant_year: int
    cp_unit: str = "ouvrables"
    main_leave_days: float | None = None
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


def _default_main_leave_days(cp_unit: str) -> float:
    return (
        LEGAL_MAIN_LEAVE_OUVRES
        if cp_unit == "ouvres"
        else LEGAL_MAIN_LEAVE_OUVRABLES
    )


def compute_fractionnement_legal(inp: FractionnementLegalInput) -> FractionnementMbcResult:
    """
    Reliquat du congé principal au 31/10, converti en jours ouvrables pour le
    barème (3 à 5 → 1 jour, 6 et plus → 2 jours).

    Les jours posés sont comptés dans l'unité de décompte de la société : les
    comparer à un plafond en jours ouvrables alors qu'ils sont saisis en jours
    ouvrés créditerait un reliquat inexistant.

    Poser 12 jours ouvrables continus en période n'éteint pas le droit : c'est
    la condition posée par l'article L3141-23 pour que le reliquat pris hors
    période ouvre droit aux jours supplémentaires.
    """
    period_start = date(inp.grant_year, *LEGAL_PERIOD_START)
    period_end = date(inp.grant_year, *LEGAL_PERIOD_END)

    taken_days = _conge_paye_days_in_range(
        inp.validated_requests, period_start, period_end
    )
    main_leave_days = (
        inp.main_leave_days
        if inp.main_leave_days is not None
        else _default_main_leave_days(inp.cp_unit)
    )
    main_taken = min(float(len(taken_days)), main_leave_days)
    remaining_main = max(0.0, main_leave_days - main_taken)

    ratio = inp.ouvres_to_ouvrables_ratio or 1.2
    remaining_ouvres = (
        round(remaining_main, 2)
        if inp.cp_unit == "ouvres"
        else round(remaining_main / ratio, 2)
    )

    return compute_fractionnement_days_mbc(
        FractionnementMbcInput(
            solde_cp_n1_ouvres=remaining_ouvres + inp.fifth_week_deduction_ouvres,
            cp_reported_june_ouvres=0.0,
            cp_seniority_deduction_ouvres=0.0,
            fifth_week_deduction_ouvres=inp.fifth_week_deduction_ouvres,
            ouvres_to_ouvrables_ratio=ratio,
        )
    )
