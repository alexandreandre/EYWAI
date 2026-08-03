"""Requêtes et calcul fractionnement CP."""

from __future__ import annotations

from datetime import date
from typing import Any

from app.core.database import supabase
from app.modules.absences.application.fractionnement_prefill import (
    resolve_fractionnement_inputs,
)
from app.modules.absences.application.queries import _leave_context, _parse_hire_date
from app.modules.absences.domain.fractionnement import (
    FractionnementMbcInput,
    compute_fractionnement_days_mbc,
    ouvrables_to_ouvres,
)
from app.modules.absences.domain.fractionnement_legal import (
    FractionnementLegalInput,
    compute_fractionnement_legal,
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
        "calculation_method": row.get("calculation_method")
        or frac_repo.DEFAULT_CALCULATION_METHOD,
        "exclude_forfait_jours": bool(row.get("exclude_forfait_jours", True)),
    }


def get_fractionnement_settings(company_id: str) -> dict[str, Any]:
    return _settings_to_api(frac_repo.get_fractionnement_settings_row(company_id))


def update_fractionnement_settings(
    company_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    row = frac_repo.upsert_fractionnement_settings(company_id, payload)
    return _settings_to_api(row)


def _solde_cp_n1_ouvres_at_date(
    employee_id: str,
    company_id: str,
    ref_date: date,
    *,
    ratio: float,
    cp_unit: str,
) -> float:
    hire_date = _parse_hire_date(employee_id)
    if not hire_date:
        return 0.0
    policy, adjustment, _, cp_seniority = _leave_context(
        employee_id, ref_date.year, company_id
    )
    from app.modules.absences.application.fractionnement_prefill import (
        build_employee_cp_seniority_context_from_db,
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
        .select("id, statut, is_forfait_jour, first_name, last_name")
        .eq("id", employee_id)
        .eq("company_id", company_id)
        .limit(1)
        .execute()
    )
    rows = emp_resp.data or []
    if not rows:
        return None
    emp = rows[0]
    if settings.get("exclude_forfait_jours", True) and is_forfait_jour(
        emp.get("statut"), emp.get("is_forfait_jour")
    ):
        return None

    ratio = settings["ouvres_to_ouvrables_ratio"]
    cp_unit = settings["cp_unit"]
    method = settings.get("calculation_method") or frac_repo.DEFAULT_CALCULATION_METHOD

    solde_n1 = _solde_cp_n1_ouvres_at_date(
        employee_id,
        company_id,
        date(grant_year, 10, 31),
        ratio=ratio,
        cp_unit=cp_unit,
    )

    inputs = resolve_fractionnement_inputs(
        company_id,
        employee_id,
        grant_year,
        ratio=ratio,
        cp_unit=cp_unit,
    )
    reported = inputs["cp_reported_june_ouvres"]
    seniority = inputs["cp_seniority_deduction_ouvres"]
    inp_row = frac_repo.get_fractionnement_input(company_id, employee_id, grant_year)
    manual_solde = float((inp_row or {}).get("manual_solde_ouvrables") or 0)

    if method == "legal":
        validated = absence_repository.list_validated_for_employees([employee_id])
        result = compute_fractionnement_legal(
            FractionnementLegalInput(
                validated_requests=validated,
                grant_year=grant_year,
                cp_unit=cp_unit,
                fifth_week_deduction_ouvres=settings["fifth_week_deduction_ouvres"],
                ouvres_to_ouvrables_ratio=ratio,
            )
        )
    elif method == "manual":
        result = compute_fractionnement_days_mbc(
            FractionnementMbcInput(
                solde_cp_n1_ouvres=manual_solde / ratio if ratio else manual_solde,
                cp_reported_june_ouvres=0,
                cp_seniority_deduction_ouvres=0,
                fifth_week_deduction_ouvres=0,
                ouvres_to_ouvrables_ratio=ratio,
            )
        )
    else:
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
        "calculation_method": method,
        "solde_ouvres": result.solde_ouvres,
        "solde_ouvrables": result.solde_ouvrables,
        "one_day_column": result.one_day_column,
        "two_days_column": result.two_days_column,
        "prefill_source": inputs.get("prefill_source"),
        "source": f"fractionnement_{method}",
    }

    return {
        "employee_id": employee_id,
        "first_name": emp.get("first_name") or "",
        "last_name": emp.get("last_name") or "",
        "grant_year": grant_year,
        "cp_reported_june_ouvres": reported,
        "cp_seniority_deduction_ouvres": seniority,
        "auto_report_june_ouvres": inputs.get("auto_report_june_ouvres"),
        "auto_seniority_deduction_ouvres": inputs.get(
            "auto_seniority_deduction_ouvres"
        ),
        "report_june_manual_override": inputs.get("report_june_manual_override"),
        "seniority_manual_override": inputs.get("seniority_manual_override"),
        "prefill_source": inputs.get("prefill_source"),
        "manual_solde_ouvrables": manual_solde,
        "solde_cp_n1_ouvres": solde_n1,
        "solde_ouvres": result.solde_ouvres,
        "solde_ouvrables": result.solde_ouvrables,
        "days_granted": result.days_granted,
        "calculation_snapshot": snapshot,
        "calculation_method": method,
    }


def apply_fractionnement_to_payslip_balances(
    employee_id: str,
    company_id: str,
    year: int,
    month: int,
    balances: dict[str, Any],
) -> dict[str, Any]:
    """
    Reporte sur le bulletin de novembre les jours de fractionnement validés.

    Lecture seule : construire un bulletin ne crée aucun droit. Un droit naît
    de la validation RH (« Valider tout » sur la campagne congés), jamais d'un
    affichage — sinon un calcul faux se figerait en base sans décision.
    """
    if month != 11:
        return balances
    settings = get_fractionnement_settings(company_id)
    if not settings["fractionnement_enabled"]:
        return balances

    grant_year = year
    existing = frac_repo.get_fractionnement_grant(employee_id, grant_year)
    if not existing or existing.get("status") != "validated":
        return balances

    days = int(existing.get("days_granted") or 0)
    snapshot = existing.get("calculation_snapshot") or {}

    if days > 0:
        cp = dict(balances.get("conges_payes") or {})
        cp["acquis"] = round(float(cp.get("acquis") or 0) + days, 2)
        cp["solde"] = round(float(cp.get("solde") or 0) + days, 2)
        balances["conges_payes"] = cp
        validated_at = (existing or {}).get("validated_at")
        balances["fractionnement"] = {
            "jours_acquis": days,
            "reference_date": f"31/10/{grant_year}",
            "libelle": f"Jour(s) de fractionnement acquis : {days}",
            "source": snapshot.get("source", "fractionnement_mbc"),
            **({"validated_at": validated_at} if validated_at else {}),
        }
    return balances


def list_fractionnement_preview(company_id: str, grant_year: int) -> list[dict[str, Any]]:
    emp_resp = (
        supabase.table("employees")
        .select("id, first_name, last_name, statut, is_forfait_jour")
        .eq("company_id", company_id)
        .in_("employment_status", ["actif", "active", "en_onboarding"])
        .execute()
    )
    rows: list[dict[str, Any]] = []
    for emp in emp_resp.data or []:
        if is_forfait_jour(emp.get("statut"), emp.get("is_forfait_jour")):
            continue
        computed = compute_fractionnement_for_employee(
            str(emp["id"]), company_id, grant_year
        )
        if computed:
            grant = frac_repo.get_fractionnement_grant(str(emp["id"]), grant_year)
            computed["status"] = (grant or {}).get("status", "computed")
            rows.append(computed)
    return rows


def upsert_fractionnement_input(
    company_id: str,
    employee_id: str,
    grant_year: int,
    cp_reported_june_ouvres: float,
    cp_seniority_deduction_ouvres: float = 0.0,
    *,
    report_june_manual_override: bool = True,
    seniority_manual_override: bool = True,
    manual_solde_ouvrables: float | None = None,
) -> dict[str, Any]:
    return frac_repo.upsert_fractionnement_input(
        company_id,
        employee_id,
        grant_year,
        cp_reported_june_ouvres,
        cp_seniority_deduction_ouvres,
        report_june_manual_override=report_june_manual_override,
        seniority_manual_override=seniority_manual_override,
        manual_solde_ouvrables=manual_solde_ouvrables,
    )


def reset_fractionnement_input_to_auto(
    company_id: str,
    employee_id: str,
    grant_year: int,
) -> dict[str, Any]:
    settings = get_fractionnement_settings(company_id)
    ratio = settings["ouvres_to_ouvrables_ratio"]
    cp_unit = settings["cp_unit"]
    auto = resolve_fractionnement_inputs(
        company_id,
        employee_id,
        grant_year,
        ratio=ratio,
        cp_unit=cp_unit,
    )
    return frac_repo.upsert_fractionnement_input(
        company_id,
        employee_id,
        grant_year,
        auto["auto_report_june_ouvres"],
        auto["auto_seniority_deduction_ouvres"],
        report_june_manual_override=False,
        seniority_manual_override=False,
    )


def validate_fractionnement_grants(
    company_id: str,
    grant_year: int,
    *,
    validated_by: str | None = None,
) -> dict[str, Any]:
    preview = list_fractionnement_preview(company_id, grant_year)
    count = 0
    for row in preview:
        frac_repo.upsert_fractionnement_grant(
            company_id,
            row["employee_id"],
            grant_year,
            grant_year,
            11,
            int(row["days_granted"]),
            row["calculation_snapshot"],
            status="validated",
            validated_by=validated_by,
        )
        count += 1
    return {"grant_year": grant_year, "validated_count": count, "status": "validated"}
