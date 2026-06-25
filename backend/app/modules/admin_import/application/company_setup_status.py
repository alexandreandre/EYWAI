"""Agrégat de complétude configuration entreprise (onboarding import)."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from app.core.database import get_supabase_admin_client
from app.modules.companies.domain.overview import is_jei_company_configured
from app.modules.dsn_import.application.coverage import (
    compute_coverage,
    count_timeline_coverage,
    is_dsn_coverage_complete,
)
from app.modules.onboarding.domain.profile import is_profile_complete, missing_payroll_fields
from app.shared.utils.iban import has_valid_iban


def _db():
    return get_supabase_admin_client()


def _company_row(company_id: str) -> Optional[Dict[str, Any]]:
    resp = (
        _db()
        .table("companies")
        .select(
            "id, company_name, siret, idcc, taux_at_mp, taux_vm, taux_fnal, "
            "paie_jour_de_fin, paie_occurrence, dsn_sync_mode"
        )
        .eq("id", company_id)
        .maybe_single()
        .execute()
    )
    return resp.data if resp and resp.data else None


def _employees_stats(company_id: str) -> Dict[str, Any]:
    resp = (
        _db()
        .table("employees")
        .select(
            "id, employment_status, "
            "coordonnees_bancaires, nir, date_naissance, adresse, salaire_de_base"
        )
        .eq("company_id", company_id)
        .execute()
    )
    rows = resp.data or []
    active = [
        r
        for r in rows
        if str(r.get("employment_status") or "actif").lower() in ("actif", "active")
    ]
    total = len(active)
    complete = 0
    missing_rib = 0
    for emp in active:
        enriched = dict(emp)
        if enriched.get("profile_complete") is None:
            enriched["profile_complete"] = is_profile_complete(enriched)
            enriched["missing_payroll_fields"] = missing_payroll_fields(enriched)
        if enriched.get("profile_complete"):
            complete += 1
        if not has_valid_iban(emp.get("coordonnees_bancaires")):
            missing_rib += 1
    pct = round(100.0 * complete / total, 1) if total else 0.0
    return {
        "total": total,
        "profile_complete_pct": pct,
        "missing_rib_count": missing_rib,
    }


def _cp_adjusted_count(company_id: str) -> int:
    resp = (
        _db()
        .table("employee_leave_adjustments")
        .select("id", count="exact")
        .eq("company_id", company_id)
        .execute()
    )
    return int(resp.count or 0)


def _leave_configured(company_id: str) -> bool:
    resp = (
        _db()
        .table("company_leave_settings")
        .select("id")
        .eq("company_id", company_id)
        .limit(1)
        .execute()
    )
    return bool(resp.data)


def _modulation_configured(company_id: str) -> bool:
    resp = (
        _db()
        .table("company_modulation_settings")
        .select("enabled")
        .eq("company_id", company_id)
        .limit(1)
        .execute()
    )
    if not resp.data:
        return False
    return bool(resp.data[0].get("enabled"))


def _jei_configured(company_id: str) -> bool:
    resp = (
        _db()
        .table("company_jei_settings")
        .select("jei_enabled, date_creation_etablissement")
        .eq("company_id", company_id)
        .limit(1)
        .maybe_single()
        .execute()
    )
    return is_jei_company_configured(resp.data if resp else None)


def _oeth_configured(company_id: str) -> bool:
    resp = (
        _db()
        .table("company_oeth_annual_reviews")
        .select("id")
        .eq("company_id", company_id)
        .limit(1)
        .execute()
    )
    return bool(resp.data)


def _planning_months(company_id: str) -> int:
    year = date.today().year
    resp = (
        _db()
        .table("employee_schedules")
        .select("month")
        .eq("company_id", company_id)
        .eq("year", year)
        .execute()
    )
    months = {int(r["month"]) for r in (resp.data or []) if r.get("month")}
    return len(months)


def _block_score(ok: bool, weight: float = 1.0) -> float:
    return weight if ok else 0.0


def _payroll_kpi_block(company_id: str) -> Dict[str, Any]:
    from app.modules.payroll.application.payroll_kpi_queries import resolve_company_payroll_kpi

    today = date.today()
    last_month = today.replace(day=1) - timedelta(days=1)
    period = f"{last_month.year}-{last_month.month:02d}"
    snap = resolve_company_payroll_kpi(company_id, period)
    return {
        "ready": snap.source != "none" and snap.gross > 0,
        "source": snap.source,
        "source_label": snap.source_label,
        "period": period,
        "gross": round(snap.gross, 2),
        "net": round(snap.net, 2),
        "partial": snap.partial,
    }


def get_company_setup_status(company_id: str) -> Dict[str, Any]:
    company = _company_row(company_id)
    if not company:
        raise LookupError("Entreprise introuvable.")

    company_with_id = {**company, "id": company_id}
    coverage = compute_coverage(company_with_id)
    emp_stats = _employees_stats(company_id)
    cp_count = _cp_adjusted_count(company_id)
    leave_ok = _leave_configured(company_id)
    modulation_ok = _modulation_configured(company_id)
    jei_ok = _jei_configured(company_id)
    oeth_ok = _oeth_configured(company_id)
    planning_months = _planning_months(company_id)

    covered_months = len(coverage.get("months_covered") or [])
    applicable_covered, applicable_total = count_timeline_coverage(coverage)
    cov_status = coverage.get("status") or "never"
    expected_last_period = coverage.get("expected_last_period")
    dsn_gaps = coverage.get("gaps") or []
    employees_empty = emp_stats["total"] == 0
    dsn_ok = is_dsn_coverage_complete(coverage) and not employees_empty
    employees_ok = emp_stats["total"] > 0 and emp_stats["profile_complete_pct"] >= 95
    cp_ok = cp_count > 0 and not employees_empty
    payroll_params_ok = company.get("taux_at_mp") is not None and company.get("paie_jour_de_fin") is not None

    weights = {
        "dsn": 25,
        "employees": 25,
        "cp": 10,
        "leave_settings": 10,
        "payroll_params": 10,
        "modulation": 5,
        "planning": 5,
        "jei": 2.5,
        "oeth": 2.5,
    }
    total_w = sum(weights.values())
    earned = (
        _block_score(dsn_ok, weights["dsn"])
        + _block_score(employees_ok, weights["employees"])
        + _block_score(cp_ok, weights["cp"])
        + _block_score(leave_ok, weights["leave_settings"])
        + _block_score(payroll_params_ok, weights["payroll_params"])
        + _block_score(modulation_ok, weights["modulation"])
        + _block_score(planning_months >= 6 and not employees_empty, weights["planning"])
        + _block_score(jei_ok, weights["jei"])
        + _block_score(oeth_ok, weights["oeth"])
    )
    overall_pct = round(100.0 * earned / total_w, 1)

    next_actions: List[Dict[str, Any]] = []
    if employees_empty:
        label = (
            "Aucun salarié — réimporter une DSN pour recréer les effectifs"
            if covered_months >= 1
            else "Importer la DSN (au moins un mois)"
        )
        next_actions.append(
            {
                "block": "employees_empty",
                "label": label,
                "tab": "dsn",
                "priority": 0,
            }
        )
    elif not dsn_ok:
        if dsn_gaps:
            label = f"Compléter la couverture DSN ({len(dsn_gaps)} mois manquant(s))"
        elif cov_status == "never":
            label = "Importer la DSN (tous les mois jusqu'au mois en cours)"
        else:
            label = (
                f"Importer les DSN manquantes ({applicable_covered}/{applicable_total} mois)"
            )
        next_actions.append(
            {
                "block": "dsn",
                "label": label,
                "tab": "dsn",
                "priority": 1,
            }
        )
    if not employees_ok and emp_stats["total"] > 0:
        next_actions.append(
            {
                "block": "employees",
                "label": "Enrichir les fiches salariés (export paie)",
                "tab": "payroll-export",
                "priority": 2,
            }
        )
    elif emp_stats["missing_rib_count"] > 0:
        next_actions.append(
            {
                "block": "employees",
                "label": f"Compléter {emp_stats['missing_rib_count']} RIB via export paie",
                "tab": "payroll-export",
                "priority": 2,
            }
        )
    if not cp_ok and emp_stats["total"] > 0:
        next_actions.append(
            {
                "block": "cp",
                "label": "Importer les soldes CP depuis bulletins PDF",
                "tab": "cp",
                "priority": 4,
            }
        )
    if not leave_ok:
        next_actions.append(
            {
                "block": "leave_settings",
                "label": "Configurer les paramètres congés / RTT",
                "tab": "params",
                "priority": 5,
            }
        )
    if not payroll_params_ok:
        next_actions.append(
            {
                "block": "payroll_params",
                "label": "Compléter les paramètres paie (AT/MP, calendrier)",
                "tab": "params",
                "priority": 6,
            }
        )
    if planning_months < 6 and emp_stats["total"] > 0:
        next_actions.append(
            {
                "block": "planning",
                "label": "Importer le calendrier (optionnel)",
                "tab": "planning",
                "priority": 7,
            }
        )

    next_actions.sort(key=lambda x: x["priority"])

    return {
        "company_id": company_id,
        "company_name": company.get("company_name") or "Entreprise",
        "idcc": company.get("idcc"),
        "overall_pct": overall_pct,
        "blocks": {
            "dsn": {
                "covered_months": covered_months,
                "applicable_months": applicable_total,
                "applicable_covered_months": applicable_covered,
                "expected_last_period": expected_last_period,
                "gaps": dsn_gaps,
                "coverage_status": cov_status,
                "complete": dsn_ok,
                "last_period": coverage.get("last_period"),
                "status": cov_status if not employees_empty else (
                    "stale" if covered_months >= 1 else cov_status
                ),
                "employees_synced": not employees_empty,
            },
            "employees": {
                "total": emp_stats["total"],
                "profile_complete_pct": emp_stats["profile_complete_pct"],
                "missing_rib_count": emp_stats["missing_rib_count"],
                "empty": employees_empty,
            },
            "cp": {
                "adjusted_count": cp_count,
                "total_active": emp_stats["total"],
            },
            "leave_settings": {"configured": leave_ok},
            "modulation": {"configured": modulation_ok},
            "planning": {"months_with_calendar": planning_months},
            "payroll_params": {
                "taux_at_mp": company.get("taux_at_mp"),
                "paie_jour_de_fin": company.get("paie_jour_de_fin"),
                "paie_occurrence": company.get("paie_occurrence"),
                "taux_vm": company.get("taux_vm"),
                "taux_fnal": company.get("taux_fnal"),
            },
            "jei": {"configured": jei_ok},
            "oeth": {"configured": oeth_ok},
        },
        "next_actions": next_actions,
        "payroll_kpi": _payroll_kpi_block(company_id),
    }
