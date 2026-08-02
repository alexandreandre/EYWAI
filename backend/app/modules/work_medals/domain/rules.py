"""Règles métier pures — médailles du travail."""

from __future__ import annotations

from datetime import date
from typing import Any, Literal

from dateutil.relativedelta import relativedelta

from app.modules.employee_exits.domain.notice_period import compute_seniority_months
from app.modules.work_medals.domain.entities import (
    CaseStatus,
    MedalLevel,
    MedalTier,
    SeniorityBasis,
)

MEDAL_LEVEL_LABELS: dict[MedalLevel, str] = {
    "argent": "Médaille d'argent",
    "vermeil": "Médaille de vermeil",
    "or": "Médaille d'or",
    "grand_or": "Grande médaille d'or",
}

RH_PENDING_STATUSES: list[CaseStatus] = ["awaiting_rh", "awaiting_employee"]

DEFAULT_TIERS: list[dict[str, Any]] = [
    {
        "level": "argent",
        "years": 20,
        "label": "Médaille d'argent (20 ans)",
        "amount_mode": "fixed",
        "amount_value": 400,
    },
    {
        "level": "vermeil",
        "years": 30,
        "label": "Médaille de vermeil (30 ans)",
        "amount_mode": "fixed",
        "amount_value": 600,
    },
    {
        "level": "or",
        "years": 35,
        "label": "Médaille d'or (35 ans)",
        "amount_mode": "fixed",
        "amount_value": 800,
    },
    {
        "level": "grand_or",
        "years": 40,
        "label": "Grande médaille d'or (40 ans)",
        "amount_mode": "fixed",
        "amount_value": 1000,
    },
]

_ALLOWED_TRANSITIONS: dict[tuple[CaseStatus, CaseStatus], Literal["system", "employee", "rh"]] = {
    ("upcoming", "awaiting_rh"): "system",
    ("awaiting_rh", "approved"): "rh",
    ("awaiting_employee", "approved"): "rh",  # legacy — avant simplification workflow
    ("approved", "paid"): "system",
    ("upcoming", "dismissed"): "rh",
    ("awaiting_employee", "dismissed"): "rh",
    ("awaiting_rh", "dismissed"): "rh",
}


def parse_tiers(raw: list[dict[str, Any]] | None) -> list[MedalTier]:
    from app.modules.work_medals.domain.entities import tier_from_dict

    source = raw if raw else DEFAULT_TIERS
    return [tier_from_dict(t) for t in source]


def career_reference_date(
    hire_date: date,
    prior_service_months: int,
    seniority_basis: SeniorityBasis,
    seniority_reference_date: date | None = None,
) -> date:
    """Point de départ de l'ancienneté selon la base retenue par l'entreprise.

    - `seniority_reference_date` : la date d'ancienneté saisie par la paie (reprise
      d'ancienneté d'un contrat ou d'un employeur précédent) ; repli sur l'embauche
      si elle n'est pas renseignée, et jamais de date postérieure à l'embauche.
    - `total_career` : embauche moins les mois de reprise saisis.
    - `company_only` : la date d'embauche.
    """
    if seniority_basis == "seniority_reference_date":
        if seniority_reference_date and seniority_reference_date < hire_date:
            return seniority_reference_date
        return hire_date
    if seniority_basis == "company_only" or prior_service_months <= 0:
        return hire_date
    return hire_date - relativedelta(months=prior_service_months)


def compute_employee_seniority_months(
    hire_date: date | None,
    prior_service_months: int,
    seniority_basis: SeniorityBasis,
    reference_date: date | None = None,
    seniority_reference_date: date | None = None,
) -> int:
    if not hire_date:
        return 0
    ref = reference_date or date.today()
    start = career_reference_date(
        hire_date, prior_service_months, seniority_basis, seniority_reference_date
    )
    return compute_seniority_months(start, ref)


def milestone_reached_date(
    hire_date: date,
    prior_service_months: int,
    seniority_basis: SeniorityBasis,
    milestone_years: int,
    seniority_reference_date: date | None = None,
) -> date:
    """Date à laquelle le palier est atteint (approximation mois)."""
    start = career_reference_date(
        hire_date, prior_service_months, seniority_basis, seniority_reference_date
    )
    return start + relativedelta(years=milestone_years)


def detect_case_status(
    seniority_months: int,
    milestone_years: int,
    reminder_months_before: int,
) -> CaseStatus | None:
    """Retourne le statut à attribuer, ou None si palier non encore dans la fenêtre."""
    threshold = milestone_years * 12
    reminder_start = max(0, threshold - reminder_months_before)
    if seniority_months >= threshold:
        return "awaiting_rh"
    if seniority_months >= reminder_start:
        return "upcoming"
    return None


def can_transition(
    current: CaseStatus,
    target: CaseStatus,
    actor: Literal["system", "employee", "rh"],
) -> bool:
    expected = _ALLOWED_TRANSITIONS.get((current, target))
    return expected == actor


def compute_tier_amount(
    tier: MedalTier,
    base_salary_monthly: float,
) -> float:
    if tier.amount_mode == "salary_months":
        return round(base_salary_monthly * tier.amount_value, 2)
    return round(tier.amount_value, 2)


def extract_base_salary(employee_row: dict[str, Any]) -> float:
    sdb = employee_row.get("salaire_de_base") or {}
    if isinstance(sdb, str):
        import json

        try:
            sdb = json.loads(sdb)
        except (json.JSONDecodeError, TypeError):
            sdb = {}
    if isinstance(sdb, dict):
        return float(sdb.get("valeur") or 0)
    return 0.0


def compute_social_tax_flag(
    amount: float,
    base_salary_monthly: float,
    payroll_year: int,
    default_is_socially_taxed: bool,
) -> bool:
    """
    Règle simplifiée BOSS 2026 :
    - 2026 : exonération sociale si montant <= salaire mensuel de base brut
    - 2027+ : soumis à cotisations
    """
    if payroll_year >= 2027:
        return True
    if base_salary_monthly <= 0:
        return default_is_socially_taxed
    return amount > base_salary_monthly


def prime_label(tier: MedalTier) -> str:
    return f"Prime médaille du travail — {tier.label}"


def medal_level_for_years(years: int) -> MedalLevel | None:
    mapping = {20: "argent", 30: "vermeil", 35: "or", 40: "grand_or"}
    return mapping.get(years)  # type: ignore[return-value]
