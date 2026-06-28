"""Préremplissage fractionnement CP depuis soldes EYWAI."""

from __future__ import annotations

from datetime import date
from typing import Any

from app.modules.absences.application.queries import _leave_context
from app.modules.absences.domain.fractionnement import ouvrables_to_ouvres
from app.modules.absences.domain.rules import compute_cp_balances_for_bulletin
from app.modules.absences.infrastructure import cp_seniority_repository as cp_repo
from app.modules.absences.infrastructure import fractionnement_repository as frac_repo
from app.modules.absences.infrastructure.repository import absence_repository


def _solde_cp_n1_at_date(
    employee_id: str,
    company_id: str,
    ref_date: date,
    *,
    ratio: float,
    cp_unit: str,
) -> float:
    from app.modules.absences.application.queries import _parse_hire_date

    hire_date = _parse_hire_date(employee_id)
    if not hire_date:
        return 0.0
    policy, adjustment, _, cp_seniority = _leave_context(
        employee_id, ref_date.year, company_id
    )
    ctx = build_employee_cp_seniority_context_from_db(employee_id)
    validated = absence_repository.list_validated_for_employees([employee_id])
    cp_lines = compute_cp_balances_for_bulletin(
        hire_date,
        validated,
        ref_date,
        policy=policy,
        adjustment=adjustment,
        cp_seniority=cp_seniority,
        employee_ctx=ctx,
    )
    solde = float(cp_lines["periode_precedente"].get("solde") or 0)
    if cp_unit == "ouvres":
        return ouvrables_to_ouvres(solde, ratio)
    return round(solde, 2)


def build_employee_cp_seniority_context_from_db(employee_id: str):
    from app.core.database import supabase
    from app.modules.absences.application.cp_seniority_queries import (
        build_employee_cp_seniority_context,
        employee_cp_seniority_select,
        employee_cp_seniority_select_without_cadre_dirigeant,
        is_missing_cadre_dirigeant_column_error,
    )

    try:
        resp = (
            supabase.table("employees")
            .select(employee_cp_seniority_select())
            .eq("id", employee_id)
            .limit(1)
            .execute()
        )
    except Exception as exc:
        if not is_missing_cadre_dirigeant_column_error(exc):
            raise
        resp = (
            supabase.table("employees")
            .select(employee_cp_seniority_select_without_cadre_dirigeant())
            .eq("id", employee_id)
            .limit(1)
            .execute()
        )
    rows = resp.data or []
    if not rows:
        from app.modules.absences.domain.cp_seniority import EmployeeCpSeniorityContext

        return EmployeeCpSeniorityContext(hire_date=None)
    return build_employee_cp_seniority_context(rows[0])


def compute_auto_report_june_ouvres(
    employee_id: str,
    company_id: str,
    grant_year: int,
    *,
    ratio: float,
    cp_unit: str,
) -> float:
    """Solde CP N-1 au 1er juin (report) converti en ouvrés."""
    return _solde_cp_n1_at_date(
        employee_id,
        company_id,
        date(grant_year, 6, 1),
        ratio=ratio,
        cp_unit=cp_unit,
    )


def compute_auto_seniority_deduction_ouvres(
    employee_id: str,
    grant_year: int,
    *,
    ratio: float,
    cp_unit: str,
) -> float:
    """Jours CP ancienneté validés, convertis en ouvrés."""
    grant = cp_repo.get_cp_seniority_grant(employee_id, grant_year)
    if not grant:
        return 0.0
    days = float(grant.get("days_granted") or 0)
    if cp_unit == "ouvrables":
        return round(days, 2)
    return ouvrables_to_ouvres(days, ratio)


def resolve_fractionnement_inputs(
    company_id: str,
    employee_id: str,
    grant_year: int,
    *,
    ratio: float,
    cp_unit: str,
) -> dict[str, Any]:
    """
    Retourne les valeurs effectives (auto ou override manuel) pour le calcul MBC.
    """
    inp_row = frac_repo.get_fractionnement_input(company_id, employee_id, grant_year)
    auto_report = compute_auto_report_june_ouvres(
        employee_id, company_id, grant_year, ratio=ratio, cp_unit=cp_unit
    )
    auto_seniority = compute_auto_seniority_deduction_ouvres(
        employee_id, grant_year, ratio=ratio, cp_unit=cp_unit
    )

    report_override = bool((inp_row or {}).get("report_june_manual_override"))
    seniority_override = bool((inp_row or {}).get("seniority_manual_override"))

    if inp_row and report_override:
        report = float(inp_row.get("cp_reported_june_ouvres") or 0)
        report_source = "manual"
    else:
        report = auto_report
        report_source = "auto"

    if inp_row and seniority_override:
        seniority = float(inp_row.get("cp_seniority_deduction_ouvres") or 0)
        seniority_source = "manual"
    else:
        seniority = auto_seniority
        seniority_source = "auto"

    return {
        "cp_reported_june_ouvres": report,
        "cp_seniority_deduction_ouvres": seniority,
        "auto_report_june_ouvres": auto_report,
        "auto_seniority_deduction_ouvres": auto_seniority,
        "report_june_manual_override": report_override,
        "seniority_manual_override": seniority_override,
        "prefill_source": {
            "report_june": report_source,
            "seniority": seniority_source,
        },
    }
