"""Détection des paliers d'ancienneté — médailles du travail."""

from __future__ import annotations

import logging
from datetime import date
from typing import Any, Dict, List

from app.core.database import supabase
from app.modules.work_medals.application import queries
from app.modules.work_medals.application.notifications import notify_employee_eligible
from app.modules.work_medals.domain.rules import (
    compute_employee_seniority_months,
    detect_case_status,
    milestone_reached_date,
    parse_tiers,
)
from app.modules.work_medals.infrastructure.repository import work_medal_cases_repository
from app.modules.work_medals.schemas.responses import WorkMedalScanResult

logger = logging.getLogger(__name__)

_ACTIVE_STATUSES = ("actif", "active", "en_onboarding")


def _parse_hire_date(raw: Any) -> date | None:
    if raw is None:
        return None
    if isinstance(raw, date):
        return raw
    if isinstance(raw, str):
        try:
            return date.fromisoformat(raw[:10])
        except (ValueError, TypeError):
            return None
    return None


def _list_active_employees(company_id: str) -> List[Dict[str, Any]]:
    res = (
        supabase.table("employees")
        .select("id, hire_date, prior_service_months, employment_status, first_name, last_name")
        .eq("company_id", company_id)
        .execute()
    )
    rows = res.data or []
    return [
        r
        for r in rows
        if (r.get("employment_status") or "actif").lower() in _ACTIVE_STATUSES
    ]


def scan_company_work_medals(company_id: str) -> WorkMedalScanResult:
    """Scanne les employés actifs et crée/met à jour les dossiers médaille."""
    settings = queries.get_work_medal_settings_raw(company_id)
    if not settings.enabled:
        return WorkMedalScanResult()

    tiers = parse_tiers([t.model_dump() for t in settings.tiers])
    created = 0
    updated = 0
    notifications_sent = 0
    today = date.today()

    for emp in _list_active_employees(company_id):
        employee_id = str(emp["id"])
        hire_date = _parse_hire_date(emp.get("hire_date"))
        if not hire_date:
            continue
        prior = int(emp.get("prior_service_months") or 0)
        seniority_months = compute_employee_seniority_months(
            hire_date,
            prior,
            settings.seniority_basis,
            today,
        )

        for tier in tiers:
            new_status = detect_case_status(
                seniority_months,
                tier.years,
                settings.reminder_months_before,
            )
            if not new_status:
                continue

            eligible = milestone_reached_date(
                hire_date,
                prior,
                settings.seniority_basis,
                tier.years,
            )
            existing = work_medal_cases_repository.get_by_employee_level(
                employee_id, tier.level
            )

            if existing:
                current_status = existing.get("status")
                if current_status in ("approved", "paid", "dismissed"):
                    continue
                patch: Dict[str, Any] = {"eligible_date": eligible.isoformat()}
                if (
                    current_status == "upcoming"
                    and new_status == "awaiting_employee"
                ):
                    patch["status"] = "awaiting_employee"
                    work_medal_cases_repository.update(str(existing["id"]), patch)
                    updated += 1
                    if notify_employee_eligible(
                        employee_id,
                        company_id,
                        tier.level,
                        eligible.isoformat(),
                    ):
                        notifications_sent += 1
                elif current_status == "upcoming":
                    work_medal_cases_repository.update(str(existing["id"]), patch)
                    updated += 1
                continue

            row = work_medal_cases_repository.insert(
                {
                    "company_id": company_id,
                    "employee_id": employee_id,
                    "medal_level": tier.level,
                    "milestone_years": tier.years,
                    "eligible_date": eligible.isoformat(),
                    "status": new_status,
                }
            )
            created += 1
            if new_status == "awaiting_employee" and notify_employee_eligible(
                employee_id,
                company_id,
                tier.level,
                eligible.isoformat(),
            ):
                notifications_sent += 1
            logger.debug(
                "[work_medals] dossier créé %s %s statut=%s",
                employee_id,
                tier.level,
                row.get("status"),
            )

    return WorkMedalScanResult(
        created=created,
        updated=updated,
        notifications_sent=notifications_sent,
    )
