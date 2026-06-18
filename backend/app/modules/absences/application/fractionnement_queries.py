"""Requêtes et calcul fractionnement CP."""

from __future__ import annotations

from datetime import date
from typing import Any

from app.core.database import supabase
from app.modules.absences.domain.fractionnement import (
    FractionnementMbcInput,
    compute_fractionnement_days_mbc,
    ouvrables_to_ouvres,
)
from app.modules.absences.domain.rules import compute_cp_balances_for_bulletin
from app.modules.absences.infrastructure import fractionnement_repository as frac_repo
from app.modules.absences.infrastructure.repository import absence_repository
from app.modules.payroll.application.payslip_commands import is_forfait_jour


def _settings_to_api(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "company_id": str(row["company_id"]),
        "fractionnement_enabled": bool(row.get("fractionnement_enabled")),
        "cp_unit": row.get("cp_unit") or "ouvres",
        "ouvres_to_ouvrables_ratio": float(
            row.get("ouvres_to_ouvrables_ratio") or 1.2
        ),
        "fifth_week_deduction_ouvres": float(
            row.get("fifth_week_deduction_ouvres") or 5
        ),
    }


def get_fractionnement_settings(company_id: str) -> dict[str, Any]:
    return _settings_to_api(frac_repo.get_fractionnement_settings_row(company_id))


def update_fractionnement_settings(
    company_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    row = frac_repo.upsert_fractionnement_settings(company_id, payload)
    return _settings_to_api(row)


def _parse_hire_date(employee_id: str) -> date | None:
    resp = (
        supabase.table("employees")
        .select("hire_date")
        .eq("id", employee_id)
        .limit(1)
        .execute()
    )
    rows = resp.data or []
    if not rows or not rows[0].get("hire_date"):
        return None
    h = rows[0]["hire_date"]
    return date.fromisoformat(h[:10]) if isinstance(h, str) else h


def _solde_cp_n1_ouvres_at_oct31(
    employee_id: str,
    grant_year: int,
    *,
    ratio: float,
    cp_unit: str,
) -> float:
    ref_date = date(grant_year, 10, 31)
    hire_date = _parse_hire_date(employee_id)
    if not hire_date:
        return 0.0
    validated = absence_repository.list_validated_for_employees([employee_id])
    cp_lines = compute_cp_balances_for_bulletin(hire_date, validated, ref_date)
    solde = float(cp_lines["periode_precedente"].get("solde") or 0)
    if cp_unit == "ouvres":
        return ouvrables_to_ouvres(solde, ratio)
    return round(solde, 2)


def compute_fractionnement_for_employee(
    employee_id: str,
    company_id: str,
    grant_year: int,
) -> dict[str, Any] | None:
    settings = get_fractionnement_settings(company_id)
    if not settings["fractionnement_enabled"]:
        return None

    emp_resp = (
        supabase.table("employees")
        .select("id, statut, first_name, last_name")
        .eq("id", employee_id)
        .eq("company_id", company_id)
        .limit(1)
        .execute()
    )
    rows = emp_resp.data or []
    if not rows:
        return None
    emp = rows[0]
    if is_forfait_jour(emp.get("statut")):
        return None

    ratio = settings["ouvres_to_ouvrables_ratio"]
    solde_n1 = _solde_cp_n1_ouvres_at_oct31(
        employee_id, grant_year, ratio=ratio, cp_unit=settings["cp_unit"]
    )
    inp_row = frac_repo.get_fractionnement_input(company_id, employee_id, grant_year)
    reported = float((inp_row or {}).get("cp_reported_june_ouvres") or 0)
    seniority = float((inp_row or {}).get("cp_seniority_deduction_ouvres") or 0)

    result = compute_fractionnement_days_mbc(
        FractionnementMbcInput(
            solde_cp_n1_ouvres=solde_n1,
            cp_reported_june_ouvres=reported,
            cp_seniority_deduction_ouvres=seniority,
            fifth_week_deduction_ouvres=settings["fifth_week_deduction_ouvres"],
            ouvres_to_ouvrables_ratio=ratio,
        )
    )

    snapshot = {
        "solde_cp_n1_ouvres": solde_n1,
        "cp_reported_june_ouvres": reported,
        "cp_seniority_deduction_ouvres": seniority,
        "fifth_week_deduction_ouvres": settings["fifth_week_deduction_ouvres"],
        "solde_ouvres": result.solde_ouvres,
        "solde_ouvrables": result.solde_ouvrables,
        "one_day_column": result.one_day_column,
        "two_days_column": result.two_days_column,
    }

    return {
        "employee_id": employee_id,
        "first_name": emp.get("first_name") or "",
        "last_name": emp.get("last_name") or "",
        "grant_year": grant_year,
        "cp_reported_june_ouvres": reported,
        "cp_seniority_deduction_ouvres": seniority,
        "solde_cp_n1_ouvres": solde_n1,
        "solde_ouvres": result.solde_ouvres,
        "solde_ouvrables": result.solde_ouvrables,
        "days_granted": result.days_granted,
        "calculation_snapshot": snapshot,
    }


def apply_fractionnement_to_payslip_balances(
    employee_id: str,
    company_id: str,
    year: int,
    month: int,
    balances: dict[str, Any],
) -> dict[str, Any]:
    """Crédite les jours de fractionnement sur le bulletin de novembre."""
    if month != 11:
        return balances
    settings = get_fractionnement_settings(company_id)
    if not settings["fractionnement_enabled"]:
        return balances

    grant_year = year
    existing = frac_repo.get_fractionnement_grant(employee_id, grant_year)
    if existing:
        days = int(existing.get("days_granted") or 0)
        snapshot = existing.get("calculation_snapshot") or {}
    else:
        computed = compute_fractionnement_for_employee(
            employee_id, company_id, grant_year
        )
        if not computed:
            return balances
        days = int(computed["days_granted"])
        snapshot = computed["calculation_snapshot"]
        frac_repo.upsert_fractionnement_grant(
            company_id,
            employee_id,
            grant_year,
            year,
            month,
            days,
            snapshot,
        )

    if days > 0:
        cp = dict(balances.get("conges_payes") or {})
        cp["acquis"] = round(float(cp.get("acquis") or 0) + days, 2)
        cp["solde"] = round(float(cp.get("solde") or 0) + days, 2)
        balances["conges_payes"] = cp
        balances["fractionnement"] = {
            "jours_acquis": days,
            "reference_date": f"31/10/{grant_year}",
            "libelle": f"Jour(s) de fractionnement acquis : {days}",
        }
    return balances


def list_fractionnement_preview(company_id: str, grant_year: int) -> list[dict[str, Any]]:
    emp_resp = (
        supabase.table("employees")
        .select("id, first_name, last_name, statut")
        .eq("company_id", company_id)
        .eq("employment_status", "actif")
        .execute()
    )
    rows: list[dict[str, Any]] = []
    for emp in emp_resp.data or []:
        if is_forfait_jour(emp.get("statut")):
            continue
        computed = compute_fractionnement_for_employee(
            str(emp["id"]), company_id, grant_year
        )
        if computed:
            rows.append(computed)
    return rows


def upsert_fractionnement_input(
    company_id: str,
    employee_id: str,
    grant_year: int,
    cp_reported_june_ouvres: float,
    cp_seniority_deduction_ouvres: float = 0.0,
) -> dict[str, Any]:
    return frac_repo.upsert_fractionnement_input(
        company_id,
        employee_id,
        grant_year,
        cp_reported_june_ouvres,
        cp_seniority_deduction_ouvres,
    )
