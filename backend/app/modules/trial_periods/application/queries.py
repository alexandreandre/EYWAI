"""Lectures des périodes d'essai pour la page de suivi."""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, Iterable, List, Optional, Set

from app.core.database import supabase
from app.modules.employees.domain.trial_period_bareme import resolve_alert_days
from app.modules.employees.domain.trial_period_shared import parse_date
from app.modules.trial_periods.domain.constants import STATUS_EN_COURS
from app.modules.trial_periods.infrastructure.repository import repository

# Huit mois : la durée maximale légale d'une période d'essai, cadre renouvelé
# une fois. Au-delà, il n'y a plus rien à qualifier.
TO_QUALIFY_WINDOW_DAYS = 240

_TRACKED_STATUSES = frozenset({"actif", "en_onboarding"})


def _end_date_key(trial: Dict[str, Any]) -> str:
    return str(trial.get("end_date") or "")


def split_sections(
    trials: Iterable[Dict[str, Any]],
    alert_days: int,
    reference: date,
) -> Dict[str, List[Dict[str, Any]]]:
    """Sépare les périodes actives entre « en cours » et « à confirmer »."""
    en_cours: List[Dict[str, Any]] = []
    a_confirmer: List[Dict[str, Any]] = []

    for trial in trials:
        if str(trial.get("status") or "") != STATUS_EN_COURS:
            continue
        end = parse_date(trial.get("end_date"))
        if end is None:
            continue
        if (end - reference).days <= alert_days:
            a_confirmer.append(trial)
        else:
            en_cours.append(trial)

    return {
        "en_cours": sorted(en_cours, key=_end_date_key),
        "a_confirmer": sorted(a_confirmer, key=_end_date_key),
    }


def select_to_qualify(
    employees: Iterable[Dict[str, Any]],
    covered_ids: Set[str],
    reference: date,
) -> List[Dict[str, Any]]:
    """Salariés actifs récemment embauchés et sans période d'essai."""
    out: List[Dict[str, Any]] = []
    for emp in employees:
        status = str(emp.get("employment_status") or "").strip().lower()
        if status not in _TRACKED_STATUSES:
            continue
        if str(emp.get("id") or "") in covered_ids:
            continue
        hire = parse_date(emp.get("hire_date"))
        if hire is None:
            continue
        if (reference - hire).days > TO_QUALIFY_WINDOW_DAYS:
            continue
        out.append(emp)
    return sorted(out, key=lambda e: str(e.get("hire_date") or ""), reverse=True)


def fetch_company_settings(company_id: str) -> Dict[str, Any]:
    res = (
        supabase.table("companies")
        .select("settings")
        .eq("id", company_id)
        .limit(1)
        .execute()
    )
    rows = res.data or []
    settings = rows[0].get("settings") if rows else None
    return settings if isinstance(settings, dict) else {}


def fetch_employees(company_id: str) -> List[Dict[str, Any]]:
    res = (
        supabase.table("employees")
        .select(
            "id, first_name, last_name, hire_date, contract_type, statut, "
            "employment_status, contract_end_date"
        )
        .eq("company_id", company_id)
        .execute()
    )
    return list(res.data or [])


def get_tracking_page(
    company_id: str,
    reference: Optional[date] = None,
) -> Dict[str, Any]:
    """Les trois sections de la page de suivi."""
    ref = reference or date.today()
    settings = fetch_company_settings(company_id)
    alert_days = resolve_alert_days(settings)

    trials = repository.list_for_company(company_id)
    sections = split_sections(trials, alert_days, ref)

    covered = {
        str(t.get("employee_id")) for t in trials if t.get("status") == STATUS_EN_COURS
    }
    to_qualify = select_to_qualify(fetch_employees(company_id), covered, ref)

    return {
        "alert_days": alert_days,
        "en_cours": sections["en_cours"],
        "a_confirmer": sections["a_confirmer"],
        "a_qualifier": to_qualify,
    }


__all__ = [
    "TO_QUALIFY_WINDOW_DAYS",
    "fetch_company_settings",
    "fetch_employees",
    "get_tracking_page",
    "select_to_qualify",
    "split_sections",
]
