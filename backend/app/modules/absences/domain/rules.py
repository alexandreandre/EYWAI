"""
Règles métier pures — migrées depuis api/routers/absences.py.

Aucun accès DB : toutes les données passent en paramètres.
"""

import math
from datetime import date

from app.modules.absences.domain.enums import SALARY_CERTIFICATE_ABSENCE_TYPES


def get_cp_reference_period(ref_date: date) -> tuple[date, date]:
    """
    Période de référence CP en cours à la date donnée (1er juin N → 31 mai N+1).

    Ex. le 15/01/2026 → 01/06/2025 – 31/05/2026 ; le 15/09/2026 → 01/06/2026 – 31/05/2027.
    """
    if ref_date.month >= 6:
        return date(ref_date.year, 6, 1), date(ref_date.year + 1, 5, 31)
    return date(ref_date.year - 1, 6, 1), date(ref_date.year, 5, 31)


def get_cp_previous_reference_period(ref_date: date) -> tuple[date, date]:
    """Période de référence CP immédiatement précédente."""
    current_start, _ = get_cp_reference_period(ref_date)
    return date(current_start.year - 1, 6, 1), date(current_start.year, 5, 31)


def _months_worked_in_period(
    hire_date: date, period_start: date, acquisition_end: date
) -> int:
    if hire_date > acquisition_end:
        return 0
    start_of_calculation = max(hire_date, period_start)
    return (
        (acquisition_end.year - start_of_calculation.year) * 12
        + (acquisition_end.month - start_of_calculation.month)
        + 1
    )


def _acquired_cp_from_months(months_worked: int) -> float:
    """2,5 jours ouvrables par mois travaillé, arrondi à l'entier supérieur (L3141-3)."""
    if months_worked <= 0:
        return 0.0
    return float(math.ceil(months_worked * 2.5))


def calculate_acquired_cp(hire_date: date, ref_date: date) -> float:
    """
    Jours de CP acquis sur la période de référence en cours, cumulés jusqu'à ref_date.

    Règle officielle : 2,5 jours ouvrables par mois de travail effectif sur la période
    1er juin → 31 mai ; chaque mois entamé compte pour un mois entier.
    """
    period_start, period_end = get_cp_reference_period(ref_date)
    acquisition_end = min(ref_date, period_end)
    months_worked = _months_worked_in_period(hire_date, period_start, acquisition_end)
    return _acquired_cp_from_months(months_worked)


def calculate_acquired_cp_for_period(
    hire_date: date, period_start: date, period_end: date
) -> float:
    """CP acquis sur une période de référence complète (ex. période N-1 clôturée)."""
    months_worked = _months_worked_in_period(hire_date, period_start, period_end)
    return _acquired_cp_from_months(months_worked)


def calculate_acquired_rtt(
    hire_date: date, today: date, rtt_annual_base: float = 10.0
) -> float:
    """
    RTT acquis pour l'année civile (prorata si embauche en cours d'année).
    FIXME: rtt_annual_base depuis config entreprise.
    """
    if hire_date.year < today.year:
        return rtt_annual_base
    months_worked_this_year = (
        (today.year - hire_date.year) * 12 + (today.month - hire_date.month) + 1
    )
    acquired_rtt = (rtt_annual_base / 12) * months_worked_this_year
    return round(acquired_rtt, 2)


def requires_salary_certificate(absence_type: str) -> bool:
    """True si le type d'absence déclenche une attestation de salaire."""
    return absence_type in SALARY_CERTIFICATE_ABSENCE_TYPES


def _parse_absence_day(value: object) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None


def count_absence_days_taken(
    requests: list[dict],
    absence_type: str,
    ref_date: date,
    *,
    period_start: date | None = None,
    period_end: date | None = None,
) -> float:
    """Jours d'absence validés pris jusqu'à ref_date, optionnellement bornés à une période."""
    effective_end = ref_date
    if period_end is not None:
        effective_end = min(ref_date, period_end)

    total = 0.0
    for req in requests:
        if req.get("type") != absence_type:
            continue
        days_in_range = []
        for day in req.get("selected_days") or []:
            parsed = _parse_absence_day(day)
            if parsed is None:
                continue
            if parsed > effective_end:
                continue
            if period_start is not None and parsed < period_start:
                continue
            days_in_range.append(parsed)

        if absence_type == "conge_paye" and req.get("jours_payes") is not None:
            total += min(len(days_in_range), float(req["jours_payes"]))
        else:
            total += len(days_in_range)
    return total


def _balance(acquis: float, pris: float) -> dict[str, float]:
    return {
        "acquis": acquis,
        "pris": pris,
        "solde": round(acquis - pris, 2),
    }


def compute_cp_balances_for_bulletin(
    hire_date: date,
    validated_requests: list[dict],
    ref_date: date,
) -> dict[str, dict[str, float | str]]:
    """
    Soldes CP pour bulletin : période en cours + période précédente si solde restant.

    Pratique paie officielle (compteur double ligne N / N-1).
    """
    current_start, current_end = get_cp_reference_period(ref_date)
    prev_start, prev_end = get_cp_previous_reference_period(ref_date)

    current = _balance(
        calculate_acquired_cp(hire_date, ref_date),
        count_absence_days_taken(
            validated_requests,
            "conge_paye",
            ref_date,
            period_start=current_start,
            period_end=current_end,
        ),
    )
    current["periode"] = (
        f"{current_start.strftime('%d/%m/%Y')} – {current_end.strftime('%d/%m/%Y')}"
    )

    prev_acquis = calculate_acquired_cp_for_period(hire_date, prev_start, prev_end)
    prev_pris = count_absence_days_taken(
        validated_requests,
        "conge_paye",
        ref_date,
        period_start=prev_start,
        period_end=prev_end,
    )
    previous = _balance(prev_acquis, prev_pris)
    previous["periode"] = (
        f"{prev_start.strftime('%d/%m/%Y')} – {prev_end.strftime('%d/%m/%Y')}"
    )

    return {
        "periode_courante": current,
        "periode_precedente": previous,
    }


def compute_absence_balances(
    hire_date: date,
    validated_requests: list[dict],
    ref_date: date,
    *,
    repos_acquis: float = 0.0,
    rtt_annual_base: float = 10.0,
) -> dict[str, dict[str, float]]:
    """Soldes CP (période courante), RTT et repos compensateur à une date de référence."""
    current_start, current_end = get_cp_reference_period(ref_date)
    cp_acquis = calculate_acquired_cp(hire_date, ref_date)
    cp_pris = count_absence_days_taken(
        validated_requests,
        "conge_paye",
        ref_date,
        period_start=current_start,
        period_end=current_end,
    )
    rtt_acquis = calculate_acquired_rtt(hire_date, ref_date, rtt_annual_base)
    rtt_pris = count_absence_days_taken(
        validated_requests,
        "rtt",
        ref_date,
        period_start=date(ref_date.year, 1, 1),
        period_end=date(ref_date.year, 12, 31),
    )
    repos_pris = count_absence_days_taken(
        validated_requests,
        "repos_compensateur",
        ref_date,
        period_start=date(ref_date.year, 1, 1),
        period_end=date(ref_date.year, 12, 31),
    )

    return {
        "conges_payes": _balance(cp_acquis, cp_pris),
        "rtt": _balance(rtt_acquis, rtt_pris),
        "repos_compensateur": _balance(repos_acquis, repos_pris),
    }
