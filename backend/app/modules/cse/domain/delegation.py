# app/modules/cse/domain/delegation.py
"""
Calcul pur des heures de délégation CSE — conforme art. R. 2314-1, L/R. 2315-5/6/8/9.
Sans I/O : testable unitairement.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, Literal, Optional, Sequence, Tuple

from app.modules.cse.domain.delegation_bareme import (
    EMPLOYER_NOTICE_DAYS,
    PLAFOND_MULTIPLIER,
    REPORT_WINDOW_MONTHS,
    TITULAIRE_ROLES,
    ZERO_CREDIT_ROLES,
    heures_mensuelles_legales,
)

DelegationHourSource = Literal["propre", "reportee", "mutualisee", "exceptionnelle"]


@dataclass(frozen=True)
class DelegationHourRecord:
    """Heure consommée (vue domaine)."""

    usage_date: date
    duration_hours: float
    source: DelegationHourSource = "propre"
    origin_month: Optional[date] = None


@dataclass(frozen=True)
class DelegationTransferRecord:
    """Mutualisation entre élus (vue domaine)."""

    period_year: int
    period_month: int
    from_employee_id: str
    to_employee_id: str
    hours: float
    employer_notified_at: Optional[date] = None


@dataclass(frozen=True)
class DelegationRequestRecord:
    """Bon de délégation prévu (L4)."""

    planned_date: date
    planned_hours: float
    status: Literal["planifie", "realise", "annule"] = "planifie"
    realized_hours: Optional[float] = None


@dataclass
class MonthlyBalanceInput:
    """Données d'entrée pour le calcul d'un mois."""

    year: int
    month: int
    role: str
    reference_headcount: int
    monthly_hours_override: Optional[float] = None
    report_enabled: bool = True
    mutualisation_enabled: bool = True
    consumed_hours: float = 0.0
    transfers_in: float = 0.0
    transfers_out: float = 0.0
    prior_monthly_unused: Dict[Tuple[int, int], float] = field(default_factory=dict)


@dataclass(frozen=True)
class MonthlyCreditDetail:
    """Détail du crédit et solde pour un mois donné."""

    year: int
    month: int
    credit_base: float
    reported_available: float
    transfers_in: float
    transfers_out: float
    monthly_cap: float
    available_hours: float
    consumed_hours: float
    remaining_hours: float
    overrun_hours: float
    is_near_limit: bool
    is_over_limit: bool
    warnings: Tuple[str, ...] = ()


def credit_base(
    role: str,
    reference_headcount: int,
    monthly_hours_override: Optional[float] = None,
) -> float:
    """
    Crédit mensuel de base d'un élu.
    Override prioritaire ; sinon barème légal pour titulaires ; 0 pour suppléants.
    """
    if monthly_hours_override is not None:
        return float(monthly_hours_override)
    role_norm = (role or "").strip().lower()
    if role_norm in TITULAIRE_ROLES:
        return heures_mensuelles_legales(reference_headcount)
    if role_norm in ZERO_CREDIT_ROLES:
        return 0.0
    return 0.0


def monthly_cap(credit_base_hours: float) -> float:
    """Plafond mensuel (1,5 × crédit de base)."""
    return round(credit_base_hours * PLAFOND_MULTIPLIER, 2)


def _month_key(year: int, month: int) -> Tuple[int, int]:
    return (year, month)


def _prior_month(year: int, month: int) -> Tuple[int, int]:
    if month == 1:
        return (year - 1, 12)
    return (year, month - 1)


def _months_in_report_window(ref_year: int, ref_month: int) -> List[Tuple[int, int]]:
    """12 mois glissants précédant ref_month (exclus le mois ref)."""
    months: List[Tuple[int, int]] = []
    y, m = ref_year, ref_month
    for _ in range(REPORT_WINDOW_MONTHS):
        y, m = _prior_month(y, m)
        months.append((y, m))
    return months


def reported_available(
    ref_year: int,
    ref_month: int,
    credit_base_hours: float,
    report_enabled: bool,
    prior_monthly_unused: Dict[Tuple[int, int], float],
) -> float:
    """
    Heures reportables disponibles pour le mois ref (somme des soldes non consommés
    des 12 mois précédents, chaque mois plafonné individuellement).
    """
    if not report_enabled or credit_base_hours <= 0:
        return 0.0
    total = 0.0
    for key in _months_in_report_window(ref_year, ref_month):
        total += max(0.0, prior_monthly_unused.get(key, 0.0))
    return round(total, 2)


def compute_monthly_balance(inp: MonthlyBalanceInput) -> MonthlyCreditDetail:
    """Calcule le détail crédit/solde pour un mois."""
    base = credit_base(inp.role, inp.reference_headcount, inp.monthly_hours_override)
    cap = monthly_cap(base)
    rep = reported_available(
        inp.year,
        inp.month,
        base,
        inp.report_enabled,
        inp.prior_monthly_unused,
    )
    tin = inp.transfers_in if inp.mutualisation_enabled else 0.0
    tout = inp.transfers_out if inp.mutualisation_enabled else 0.0

    raw_available = base + rep + tin
    capped_available = min(raw_available, cap) if cap > 0 else raw_available
    available = round(max(0.0, capped_available - tout), 2)
    consumed = round(inp.consumed_hours, 2)
    remaining = round(max(0.0, available - consumed), 2)
    overrun = round(max(0.0, consumed - available), 2)

    warnings: List[str] = []
    if overrun > 0:
        warnings.append(
            f"Dépassement de {overrun:.1f} h (circonstances exceptionnelles possibles)."
        )
    near_threshold = available * 0.8 if available > 0 else 0
    is_near = consumed >= near_threshold and overrun == 0 and available > 0
    if is_near:
        warnings.append("Approche du plafond mensuel.")

    return MonthlyCreditDetail(
        year=inp.year,
        month=inp.month,
        credit_base=base,
        reported_available=rep,
        transfers_in=round(tin, 2),
        transfers_out=round(tout, 2),
        monthly_cap=cap,
        available_hours=available,
        consumed_hours=consumed,
        remaining_hours=remaining,
        overrun_hours=overrun,
        is_near_limit=is_near,
        is_over_limit=overrun > 0,
        warnings=tuple(warnings),
    )


def compute_rolling_balances(
    role: str,
    reference_headcount: int,
    monthly_hours_override: Optional[float],
    report_enabled: bool,
    mutualisation_enabled: bool,
    monthly_consumed: Dict[Tuple[int, int], float],
    monthly_transfers_in: Dict[Tuple[int, int], float],
    monthly_transfers_out: Dict[Tuple[int, int], float],
    months: Sequence[Tuple[int, int]],
) -> Dict[Tuple[int, int], MonthlyCreditDetail]:
    """
    Calcule les soldes pour une séquence de mois (ordre chronologique).
    Chaque mois utilise les soldes non consommés des mois précédents pour le report.
    """
    credit_base(role, reference_headcount, monthly_hours_override)
    prior_unused: Dict[Tuple[int, int], float] = {}
    results: Dict[Tuple[int, int], MonthlyCreditDetail] = {}

    for year, month in sorted(months):
        key = _month_key(year, month)
        detail = compute_monthly_balance(
            MonthlyBalanceInput(
                year=year,
                month=month,
                role=role,
                reference_headcount=reference_headcount,
                monthly_hours_override=monthly_hours_override,
                report_enabled=report_enabled,
                mutualisation_enabled=mutualisation_enabled,
                consumed_hours=monthly_consumed.get(key, 0.0),
                transfers_in=monthly_transfers_in.get(key, 0.0),
                transfers_out=monthly_transfers_out.get(key, 0.0),
                prior_monthly_unused=dict(prior_unused),
            )
        )
        results[key] = detail
        prior_unused[key] = detail.remaining_hours

    return results


def validate_transfer(
    from_role: str,
    from_credit_base: float,
    to_credit_base: float,
    hours: float,
    to_month_consumed: float,
    to_month_transfers_in: float,
    to_month_reported: float,
    employer_notified_at: Optional[date],
    usage_date: date,
) -> Tuple[bool, List[str]]:
    """
    Valide une mutualisation. Retourne (ok, warnings).
    Ne bloque pas les dépassements — avertit seulement.
    """
    warnings: List[str] = []
    from_role_norm = (from_role or "").strip().lower()
    if from_role_norm not in TITULAIRE_ROLES:
        return False, ["Seul un titulaire peut céder des heures de délégation."]
    if hours <= 0:
        return False, ["Le nombre d'heures doit être strictement positif."]
    if hours > from_credit_base:
        warnings.append(
            "La cession dépasse le crédit mensuel de base du cédant "
            "(heures reportées non cédables)."
        )
    to_cap = monthly_cap(to_credit_base)
    to_total = to_credit_base + to_month_reported + to_month_transfers_in + hours
    if to_total > to_cap:
        warnings.append(
            f"Le bénéficiaire dépasserait le plafond mensuel de {to_cap:.1f} h."
        )
    if employer_notified_at is None:
        warnings.append(
            f"L'employeur doit être informé par écrit au moins "
            f"{EMPLOYER_NOTICE_DAYS} jours avant utilisation."
        )
    elif (usage_date - employer_notified_at).days < EMPLOYER_NOTICE_DAYS:
        warnings.append(
            f"Information employeur insuffisante "
            f"(minimum {EMPLOYER_NOTICE_DAYS} jours calendaires)."
        )
    return True, warnings


def aggregate_hours_by_month(
    hours: Sequence[DelegationHourRecord],
) -> Dict[Tuple[int, int], float]:
    """Agrège les heures consommées par (année, mois)."""
    out: Dict[Tuple[int, int], float] = {}
    for h in hours:
        key = (h.usage_date.year, h.usage_date.month)
        out[key] = out.get(key, 0.0) + h.duration_hours
    return out


def aggregate_transfers_by_month(
    transfers: Sequence[DelegationTransferRecord],
    direction: Literal["in", "out"],
    employee_id: str,
) -> Dict[Tuple[int, int], float]:
    """Agrège les mutualisations entrantes ou sortantes par mois."""
    out: Dict[Tuple[int, int], float] = {}
    for t in transfers:
        key = (t.period_year, t.period_month)
        if direction == "in" and t.to_employee_id == employee_id:
            out[key] = out.get(key, 0.0) + t.hours
        elif direction == "out" and t.from_employee_id == employee_id:
            out[key] = out.get(key, 0.0) + t.hours
    return out


def annual_register_row(
    year: int,
    monthly_details: Dict[Tuple[int, int], MonthlyCreditDetail],
) -> Dict[str, float]:
    """Ligne de registre annuel pour un élu."""
    year_details = [d for (y, _), d in monthly_details.items() if y == year]
    if not year_details:
        return {
            "theoretical_credit": 0.0,
            "consumed": 0.0,
            "reported_used": 0.0,
            "mutualised_received": 0.0,
            "mutualised_given": 0.0,
            "overrun": 0.0,
            "remaining_end_year": 0.0,
        }
    return {
        "theoretical_credit": round(sum(d.credit_base for d in year_details), 2),
        "consumed": round(sum(d.consumed_hours for d in year_details), 2),
        "reported_used": round(sum(d.reported_available for d in year_details), 2),
        "mutualised_received": round(sum(d.transfers_in for d in year_details), 2),
        "mutualised_given": round(sum(d.transfers_out for d in year_details), 2),
        "overrun": round(sum(d.overrun_hours for d in year_details), 2),
        "remaining_end_year": round(
            year_details[-1].remaining_hours if year_details else 0.0, 2
        ),
    }
