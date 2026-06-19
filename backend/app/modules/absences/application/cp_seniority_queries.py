"""Requêtes CP ancienneté."""

from __future__ import annotations

from datetime import date
from typing import Any

from app.core.database import supabase
from app.modules.absences.domain.cp_seniority import (
    CpSenioritySettings,
    EmployeeCpSeniorityContext,
    compute_cp_seniority_grant,
    resolve_forfait_annual_days,
)
from app.modules.absences.domain.cp_seniority_resolver import (
    recommended_preset_for_idcc,
    resolve_barème_from_cc,
)
from app.modules.absences.domain.leave_policy import LeavePolicySettings
from app.modules.absences.infrastructure import cp_seniority_repository as repo
from app.modules.absences.infrastructure.leave_settings_repository import (
    get_leave_policy,
)
from app.modules.collective_agreements.application.idcc_resolution import (
    resolve_employee_idcc,
)


def _rules_to_api(settings: CpSenioritySettings) -> dict[str, Any]:
    from app.modules.absences.domain.cp_seniority import resolve_effective_rules

    rules = resolve_effective_rules(settings)
    return {
        "mode": rules.mode,
        "tiers": [
            {
                "category": t.category,
                "min_years": t.min_years,
                "days": t.days,
                "min_age": t.min_age,
                "max_years": t.max_years,
            }
            for t in rules.tiers
        ],
    }


def _settings_to_api(company_id: str, settings: CpSenioritySettings) -> dict[str, Any]:
    row = repo.get_cp_seniority_settings_row(company_id)
    configured = row is not None
    recommended = None
    co_rows: list[dict[str, Any]] = []
    try:
        co_resp = (
            supabase.table("companies")
            .select("id, idcc")
            .eq("id", company_id)
            .limit(1)
            .execute()
        )
        co_rows = co_resp.data or []
        if co_rows:
            idcc = resolve_employee_idcc({}, co_rows[0])
            if not configured:
                recommended = recommended_preset_for_idcc(idcc)
    except Exception:
        pass
    rules_source = "custom"
    if settings.preset != "custom":
        rules_source = f"preset_{settings.preset}"
    elif configured:
        try:
            idcc = resolve_employee_idcc({}, (co_rows or [{}])[0] if co_rows else {})
            _, src = resolve_barème_from_cc(idcc)
            if src:
                rules_source = src
        except Exception:
            pass
    return {
        "company_id": company_id,
        "enabled": settings.enabled,
        "configured": configured,
        "preset": settings.preset,
        "seniority_reference": settings.seniority_reference,
        "seniority_basis": settings.seniority_basis,
        "counting_unit": settings.counting_unit,
        "rules": _rules_to_api(settings),
        "forfait_annual_days_default": settings.forfait_annual_days_default,
        "forfait_reduction_enabled": settings.forfait_reduction_enabled,
        "company_agreement_overrides": settings.company_agreement_overrides,
        "recommended_preset": recommended,
        "rules_source": rules_source,
    }


def get_cp_seniority_settings(company_id: str) -> dict[str, Any]:
    settings = repo.get_cp_seniority_settings(company_id)
    return _settings_to_api(company_id, settings)


def build_employee_cp_seniority_context(
    employee_row: dict[str, Any],
) -> EmployeeCpSeniorityContext:
    hire_raw = employee_row.get("hire_date")
    hire_date = None
    if hire_raw:
        hire_date = (
            date.fromisoformat(hire_raw[:10])
            if isinstance(hire_raw, str)
            else hire_raw
        )
    birth_raw = employee_row.get("date_naissance")
    birth_date = None
    if birth_raw:
        birth_date = (
            date.fromisoformat(birth_raw[:10])
            if isinstance(birth_raw, str)
            else birth_raw
        )
    seniority_ref_raw = employee_row.get("seniority_reference_date")
    seniority_reference_date_val = None
    if seniority_ref_raw:
        seniority_reference_date_val = (
            date.fromisoformat(seniority_ref_raw[:10])
            if isinstance(seniority_ref_raw, str)
            else seniority_ref_raw
        )
    spec = employee_row.get("specificites_paie") or {}
    forfait_override = None
    if isinstance(spec, dict) and spec.get("forfait_annual_days") is not None:
        forfait_override = float(spec["forfait_annual_days"])
    return EmployeeCpSeniorityContext(
        hire_date=hire_date,
        birth_date=birth_date,
        seniority_reference_date=seniority_reference_date_val,
        statut=employee_row.get("statut"),
        prior_service_months=int(employee_row.get("prior_service_months") or 0),
        is_cadre_dirigeant=bool(employee_row.get("is_cadre_dirigeant")),
        forfait_annual_days_override=forfait_override,
    )


def load_employee_cp_seniority_context(employee_id: str) -> EmployeeCpSeniorityContext:
    resp = (
        supabase.table("employees")
        .select(
            "hire_date, date_naissance, statut, prior_service_months, "
            "specificites_paie, seniority_reference_date, is_cadre_dirigeant"
        )
        .eq("id", employee_id)
        .limit(1)
        .execute()
    )
    rows = resp.data or []
    if not rows:
        return EmployeeCpSeniorityContext(hire_date=None)
    return build_employee_cp_seniority_context(rows[0])


def compute_and_persist_grant(
    company_id: str,
    employee_id: str,
    settings: CpSenioritySettings,
    ctx: EmployeeCpSeniorityContext,
    ref_date: date,
    policy: LeavePolicySettings | None = None,
) -> dict[str, Any]:
    grant = compute_cp_seniority_grant(settings, ctx, ref_date, policy=policy)
    if settings.is_active:
        repo.upsert_cp_seniority_grant(
            company_id,
            employee_id,
            grant.grant_year,
            grant.days_granted,
            grant.category,
            grant.seniority_years_at_ref,
            grant.forfait_days_reduction,
            grant.to_snapshot(),
        )
    return {
        "grant": grant,
        "forfait_annual_days_adjusted": resolve_forfait_annual_days(
            settings, ctx, grant
        ),
    }


def list_cp_seniority_preview(
    company_id: str, grant_year: int
) -> list[dict[str, Any]]:
    settings = repo.get_cp_seniority_settings(company_id)
    policy = get_leave_policy(company_id)
    ref_date = date(grant_year, 5, 31)

    emp_resp = (
        supabase.table("employees")
        .select(
            "id, first_name, last_name, statut, hire_date, date_naissance, "
            "prior_service_months, specificites_paie, seniority_reference_date, "
            "is_cadre_dirigeant, employment_status"
        )
        .eq("company_id", company_id)
        .in_("employment_status", ["actif", "active", "en_onboarding"])
        .execute()
    )
    rows: list[dict[str, Any]] = []
    for emp in emp_resp.data or []:
        ctx = build_employee_cp_seniority_context(emp)
        result = compute_and_persist_grant(
            company_id, str(emp["id"]), settings, ctx, ref_date, policy=policy
        )
        grant = result["grant"]
        rows.append(
            {
                "employee_id": str(emp["id"]),
                "first_name": emp.get("first_name") or "",
                "last_name": emp.get("last_name") or "",
                "statut": emp.get("statut"),
                "category": grant.category,
                "seniority_years_at_ref": grant.seniority_years_at_ref,
                "days_granted": grant.days_granted,
                "days_before_prorata": grant.days_before_prorata,
                "prorata_applied": grant.prorata_applied,
                "forfait_days_reduction": grant.forfait_days_reduction,
                "forfait_annual_days_adjusted": result["forfait_annual_days_adjusted"],
                "reference_date": grant.reference_date.isoformat(),
                "tier_matched": grant.tier_matched,
                "warnings": list(grant.warnings),
                "status": (
                    repo.get_cp_seniority_grant(str(emp["id"]), grant_year) or {}
                ).get("status", "computed"),
            }
        )
    return rows


def get_forfait_annual_days_adjusted(
    employee_id: str,
    company_id: str,
    year: int,
) -> float | None:
    settings = repo.get_cp_seniority_settings(company_id)
    if not settings.is_active or not settings.forfait_reduction_enabled:
        return None
    ctx = load_employee_cp_seniority_context(employee_id)
    if not ctx.is_forfait:
        return None
    grant_row = repo.get_cp_seniority_grant(employee_id, year)
    if grant_row:
        base = ctx.forfait_annual_days_override or settings.forfait_annual_days_default
        reduction = float(grant_row.get("forfait_days_reduction") or 0)
        return max(0.0, round(base - reduction, 2))
    policy = get_leave_policy(company_id)
    ref_date = date(year, 5, 31)
    grant = compute_cp_seniority_grant(settings, ctx, ref_date, policy=policy)
    return resolve_forfait_annual_days(settings, ctx, grant)
