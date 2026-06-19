"""Tableau de bord campagne congés annuelle (CP anc. juin, fractionnement oct.)."""

from __future__ import annotations

from datetime import date
from typing import Any

from app.modules.absences.application import (
    cp_seniority_queries,
    fractionnement_queries,
)
from app.modules.absences.infrastructure import cp_seniority_repository as cp_repo
from app.modules.absences.infrastructure import fractionnement_repository as frac_repo


def _current_phase(today: date | None = None) -> str:
    today = today or date.today()
    m = today.month
    if m in (5, 6):
        return "cp_seniority"
    if m in (10, 11):
        return "fractionnement"
    return "monitoring"


def get_leave_campaign_dashboard(
    company_id: str,
    grant_year: int | None = None,
) -> dict[str, Any]:
    today = date.today()
    grant_year = grant_year or today.year
    phase = _current_phase(today)

    cp_settings = cp_repo.get_cp_seniority_settings(company_id)
    frac_settings = frac_repo.get_fractionnement_settings_row(company_id)

    cp_preview = (
        cp_seniority_queries.list_cp_seniority_preview(company_id, grant_year)
        if cp_settings.is_active
        else []
    )
    frac_preview = (
        fractionnement_queries.list_fractionnement_preview(company_id, grant_year)
        if frac_settings.get("fractionnement_enabled")
        else []
    )

    cp_grants = cp_repo.list_cp_seniority_grants_for_company(company_id, grant_year)
    validated_cp = sum(1 for g in cp_grants if g.get("status") == "validated")
    overridden_cp = sum(1 for g in cp_grants if g.get("status") == "overridden")
    warnings_cp = sum(1 for r in cp_preview if r.get("warnings"))

    frac_grants_count = sum(
        1
        for r in frac_preview
        if (frac_repo.get_fractionnement_grant(r["employee_id"], grant_year) or {}).get(
            "status"
        )
        == "validated"
    )

    return {
        "grant_year": grant_year,
        "phase": phase,
        "today": today.isoformat(),
        "cp_seniority": {
            "enabled": cp_settings.is_active,
            "preset": cp_settings.preset,
            "employee_count": len(cp_preview),
            "total_days": round(sum(r.get("days_granted", 0) for r in cp_preview), 2),
            "validated_count": validated_cp,
            "overridden_count": overridden_cp,
            "warnings_count": warnings_cp,
            "deadline": f"{grant_year}-05-31",
        },
        "fractionnement": {
            "enabled": bool(frac_settings.get("fractionnement_enabled")),
            "calculation_method": frac_settings.get("calculation_method") or "mbc",
            "employee_count": len(frac_preview),
            "total_days": sum(r.get("days_granted", 0) for r in frac_preview),
            "validated_count": frac_grants_count,
            "deadline": f"{grant_year}-10-31",
        },
        "alerts": _build_alerts(phase, cp_settings.is_active, frac_settings, today),
    }


def _build_alerts(
    phase: str,
    cp_enabled: bool,
    frac_settings: dict[str, Any],
    today: date,
) -> list[dict[str, str]]:
    alerts: list[dict[str, str]] = []
    if phase == "cp_seniority":
        if not cp_enabled:
            alerts.append(
                {
                    "level": "warning",
                    "code": "cp_seniority_disabled",
                    "message": "Les CP ancienneté ne sont pas activés pour cette entreprise.",
                }
            )
        elif today.month == 5 and today.day >= 15:
            alerts.append(
                {
                    "level": "info",
                    "code": "cp_seniority_deadline_soon",
                    "message": "Fin de période de référence le 31 mai — validez les CP ancienneté.",
                }
            )
    if phase == "fractionnement":
        if not frac_settings.get("fractionnement_enabled"):
            alerts.append(
                {
                    "level": "warning",
                    "code": "fractionnement_disabled",
                    "message": "Le fractionnement CP n'est pas activé.",
                }
            )
        elif today.month == 10 and today.day >= 15:
            alerts.append(
                {
                    "level": "info",
                    "code": "fractionnement_deadline_soon",
                    "message": "Bilan fractionnement au 31 octobre — validez avant la paie de novembre.",
                }
            )
    return alerts
