"""Moteur de calcul OETH (EMA, contribution, déductions)."""

from __future__ import annotations

import calendar
from datetime import date
from typing import Any, Dict, List, Optional

from app.modules.oeth_settings.domain import rules
from app.modules.oeth_settings.domain.constants import DEFAULT_OETH_CONFIG


def _parse_date(value: Any) -> Optional[date]:
    if not value:
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def monthly_etp(
    hire_date: Optional[date],
    end_date: Optional[date],
    year: int,
    month: int,
) -> float:
    """ETP mensuel = jours présence / jours calendaires du mois."""
    month_start = date(year, month, 1)
    month_end = date(year, month, calendar.monthrange(year, month)[1])
    debut = max(month_start, hire_date) if hire_date else month_start
    fin = min(month_end, end_date) if end_date else month_end
    if fin < debut:
        return 0.0
    jours_mois = (month_end - month_start).days + 1
    jours_presence = (fin - debut).days + 1
    return jours_presence / jours_mois


def boeth_active_in_month(
    boeth_code: Optional[str],
    valid_from: Optional[date],
    valid_to: Optional[date],
    year: int,
    month: int,
) -> bool:
    if not boeth_code:
        return False
    month_start = date(year, month, 1)
    month_end = date(year, month, calendar.monthrange(year, month)[1])
    if valid_from and valid_from > month_end:
        return False
    if valid_to and valid_to < month_start:
        return False
    return True


def compute_ema_from_employees(
    employees: List[Dict[str, Any]],
    employment_year: int,
    ecap_job_codes: Optional[set[str]] = None,
) -> Dict[str, float]:
    """Calcule EMA assujettissement, BOETH interne et ECAP sur 12 mois."""
    ecap_codes = ecap_job_codes or set()
    sum_assuj = 0.0
    sum_boeth = 0.0
    sum_ecap = 0.0

    for emp in employees:
        hire = _parse_date(emp.get("hire_date"))
        end = _parse_date(emp.get("end_date") or emp.get("contract_end_date"))
        boeth = emp.get("boeth") or {}
        boeth_code = boeth.get("boeth_code")
        valid_from = _parse_date(boeth.get("valid_from"))
        valid_to = _parse_date(boeth.get("valid_to"))
        birth = _parse_date(emp.get("date_naissance"))
        job_code = str(emp.get("job_code") or emp.get("pcs_code") or "")

        for month in range(1, 13):
            etp = monthly_etp(hire, end, employment_year, month)
            if etp <= 0:
                continue
            sum_assuj += etp
            if boeth_active_in_month(boeth_code, valid_from, valid_to, employment_year, month):
                factor = rules.boeth_50_plus_factor(
                    birth, employment_year, DEFAULT_OETH_CONFIG
                )
                sum_boeth += etp * factor
            if job_code and job_code in ecap_codes:
                sum_ecap += etp

    return {
        "ema_assujettissement": round(sum_assuj / 12, 4),
        "ema_boeth_interne": round(sum_boeth / 12, 4),
        "ema_ecap": round(sum_ecap / 12, 4),
    }


def compute_surcontribution(
    review_history: List[Dict[str, Any]],
    employment_year: int,
    config: dict,
) -> bool:
    """Surcontribution si aucune action sur 3 années consécutives."""
    years_needed = int(config.get("surcontribution_years", 3))
    prior_years = sorted(
        [
            r
            for r in review_history
            if r.get("employment_year", 0) < employment_year
        ],
        key=lambda r: r.get("employment_year", 0),
        reverse=True,
    )[:years_needed]
    if len(prior_years) < years_needed:
        return False
    for r in prior_years:
        boeth_employed = float(r.get("ema_boeth_interne") or 0) + float(
            r.get("ema_boeth_externe") or 0
        )
        deductions = r.get("deductions_detail") or {}
        has_action = (
            boeth_employed > 0
            or float(deductions.get("061") or 0) > 0
            or float(deductions.get("062") or 0) > 0
            or float(deductions.get("063") or 0) > 0
            or float(deductions.get("064") or 0) > 0
            or r.get("accord_agree_active")
        )
        if has_action:
            return False
    return True


def compute_annual_contribution(
    *,
    employment_year: int,
    ema_assujettissement: float,
    ema_boeth_interne: float,
    ema_boeth_externe: float,
    ema_ecap: float,
    smic_horaire: float,
    taux_obligation: float,
    deductions: Dict[str, float],
    config: dict,
    neutralisation_active: bool = False,
    surcontribution_applicable: bool = False,
    accord_agree_active: bool = False,
) -> Dict[str, Any]:
    """Calcule contribution brute, nette et due."""
    quota = rules.quota_boeth(ema_assujettissement, taux_obligation)
    boeth_total = ema_boeth_interne + ema_boeth_externe
    manquants = max(0, quota - int(boeth_total))

    coeff = (
        int(config.get("coefficients", {}).get("surcontribution", 1500))
        if surcontribution_applicable
        else rules.coefficient_taille(ema_assujettissement, config)
    )
    contribution_brute = rules.round_euro(manquants * coeff * smic_horaire)

    ecap_factor = float(config.get("ecap_deduction_factor", 17))
    deduction_ecap = rules.round_euro(ema_ecap * ecap_factor * smic_horaire)
    deduction_061 = rules.round_euro(float(deductions.get("061") or 0))
    deduction_062 = rules.round_euro(float(deductions.get("062") or 0))
    deduction_063 = rules.round_euro(float(deductions.get("063") or 0))
    deduction_064 = rules.round_euro(float(deductions.get("064") or 0))

    total_deductions = deduction_ecap + deduction_061 + deduction_062 + deduction_063 + deduction_064
    if accord_agree_active:
        total_deductions = 0.0

    contribution_nette = rules.round_euro(max(0.0, contribution_brute - total_deductions))

    if neutralisation_active or accord_agree_active:
        contribution_due = 0.0
    else:
        contribution_due = contribution_nette

    return {
        "quota_boeth": quota,
        "boeth_manquants": manquants,
        "coefficient": coeff,
        "contribution_brute": contribution_brute,
        "contribution_nette": contribution_nette,
        "contribution_due": contribution_due,
        "deductions_detail": {
            "060": deduction_ecap,
            "061": deduction_061,
            "062": deduction_062,
            "063": deduction_063,
            "064": deduction_064,
            "total": rules.round_euro(total_deductions),
        },
        "taux_emploi_pct": round(
            (boeth_total / ema_assujettissement * 100) if ema_assujettissement > 0 else 0.0,
            2,
        ),
    }
