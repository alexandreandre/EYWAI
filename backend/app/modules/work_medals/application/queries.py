"""Lecture médailles du travail."""

from __future__ import annotations

from typing import List, Optional

from app.modules.work_medals.domain.rules import DEFAULT_TIERS, RH_PENDING_STATUSES, parse_tiers
from app.modules.work_medals.infrastructure.repository import (
    work_medal_cases_repository,
    work_medal_settings_repository,
)
from app.modules.work_medals.schemas.responses import (
    MedalTier,
    WorkMedalCase,
    WorkMedalSettings,
    WorkMedalSummary,
)


def _settings_from_row(company_id: str, raw: dict | None) -> WorkMedalSettings:
    if not raw:
        return WorkMedalSettings(
            company_id=company_id,
            tiers=[MedalTier.model_validate(t) for t in DEFAULT_TIERS],
        )
    tiers_raw = raw.get("tiers") or []
    tiers = [
        MedalTier(
            level=t.level,
            years=t.years,
            label=t.label,
            amount_mode=t.amount_mode,
            amount_value=t.amount_value,
        )
        for t in parse_tiers(tiers_raw)
    ]
    data = {**raw, "tiers": [t.model_dump() for t in tiers]}
    settings = WorkMedalSettings.model_validate(data)
    settings.tiers = tiers
    return settings


def get_work_medal_settings(company_id: str) -> WorkMedalSettings:
    raw = work_medal_settings_repository.get_by_company(company_id)
    return _settings_from_row(company_id, raw)


def get_work_medal_settings_raw(company_id: str) -> WorkMedalSettings:
    return get_work_medal_settings(company_id)


def list_work_medal_cases(
    company_id: str,
    *,
    status: str | None = None,
    medal_level: str | None = None,
) -> List[WorkMedalCase]:
    work_medal_cases_repository.migrate_legacy_employee_pending(company_id)
    statuses: List[str] | None = None
    status_filter = status
    if status == "awaiting_rh":
        statuses = list(RH_PENDING_STATUSES)
        status_filter = None
    rows = work_medal_cases_repository.list_by_company(
        company_id,
        status=status_filter,
        statuses=statuses,
        medal_level=medal_level,
    )
    return [WorkMedalCase.model_validate(r) for r in rows]


def list_employee_work_medal_cases(employee_id: str) -> List[WorkMedalCase]:
    rows = work_medal_cases_repository.list_by_employee(employee_id)
    if rows:
        work_medal_cases_repository.migrate_legacy_employee_pending(str(rows[0]["company_id"]))
        rows = work_medal_cases_repository.list_by_employee(employee_id)
    return [WorkMedalCase.model_validate(r) for r in rows]


def get_work_medal_case(case_id: str) -> Optional[WorkMedalCase]:
    row = work_medal_cases_repository.get_by_id(case_id)
    return WorkMedalCase.model_validate(row) if row else None


def get_work_medal_summary(company_id: str) -> WorkMedalSummary:
    settings = get_work_medal_settings(company_id)
    if not settings.enabled:
        return WorkMedalSummary()
    work_medal_cases_repository.migrate_legacy_employee_pending(company_id)
    awaiting_rh = work_medal_cases_repository.count_by_status(
        company_id, ["awaiting_rh"]
    )
    upcoming = work_medal_cases_repository.count_by_status(company_id, ["upcoming"])
    return WorkMedalSummary(
        awaiting_rh=awaiting_rh,
        awaiting_employee=0,
        upcoming=upcoming,
        total_actionable=awaiting_rh,
    )
