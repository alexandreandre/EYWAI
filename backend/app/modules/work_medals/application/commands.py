"""Commandes d'écriture — médailles du travail."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from app.core.database import supabase
from app.modules.monthly_inputs.application.commands import create_employee_monthly_input
from app.modules.monthly_inputs.schemas.requests import MonthlyInputCreate
from app.modules.work_medals.application import queries
from app.modules.work_medals.application.notifications import notify_employee_approved
from app.modules.work_medals.domain.rules import (
    can_transition,
    compute_social_tax_flag,
    compute_tier_amount,
    extract_base_salary,
    parse_tiers,
    prime_label,
)
from app.modules.work_medals.infrastructure.repository import (
    work_medal_cases_repository,
    work_medal_settings_repository,
)
from app.modules.work_medals.schemas.requests import (
    WorkMedalApproveRequest,
    WorkMedalDismissRequest,
    WorkMedalSettingsUpdate,
)
from app.modules.work_medals.schemas.responses import WorkMedalCase, WorkMedalSettings

_DB_WRITABLE_KEYS = frozenset(
    {
        "enabled",
        "seniority_basis",
        "reminder_months_before",
        "tiers",
        "default_is_taxable",
        "default_is_socially_taxed",
    }
)


def save_work_medal_settings(
    company_id: str, data: WorkMedalSettingsUpdate
) -> WorkMedalSettings:
    from app.modules.work_medals.application import detection

    current = queries.get_work_medal_settings(company_id)
    was_enabled = current.enabled
    merged: Dict[str, Any] = current.model_dump(mode="json")
    patch = data.model_dump(exclude_unset=True)
    if "tiers" in patch and patch["tiers"] is not None:
        patch["tiers"] = patch["tiers"]
    merged.update(patch)

    if merged.get("enabled") and not merged.get("tiers"):
        from app.modules.work_medals.domain.rules import DEFAULT_TIERS

        merged["tiers"] = DEFAULT_TIERS

    payload = {k: merged[k] for k in _DB_WRITABLE_KEYS if k in merged}
    row = work_medal_settings_repository.upsert(company_id, payload)
    settings = queries._settings_from_row(company_id, row)
    if not was_enabled and settings.enabled:
        detection.scan_company_work_medals(company_id)
    return settings


def _get_employee_row(employee_id: str) -> Dict[str, Any]:
    r = (
        supabase.table("employees")
        .select("id, company_id, salaire_de_base, hire_date, prior_service_months")
        .eq("id", employee_id)
        .maybe_single()
        .execute()
    )
    if not r or not r.data:
        raise ValueError("Employé introuvable")
    return r.data


def _tier_for_case(settings: WorkMedalSettings, medal_level: str):
    tiers = parse_tiers([t.model_dump() for t in settings.tiers])
    for tier in tiers:
        if tier.level == medal_level:
            return tier
    raise ValueError(f"Palier {medal_level} non configuré")


def approve_work_medal_case(
    case_id: str,
    company_id: str,
    rh_user_id: str,
    body: WorkMedalApproveRequest,
) -> WorkMedalCase:
    case = queries.get_work_medal_case(case_id)
    if not case or case.company_id != company_id:
        raise ValueError("Dossier introuvable")
    if not can_transition(case.status, "approved", "rh"):
        raise ValueError(f"Validation impossible depuis le statut {case.status}")

    settings = queries.get_work_medal_settings_raw(company_id)
    tier = _tier_for_case(settings, case.medal_level)
    employee = _get_employee_row(case.employee_id)
    base_salary = extract_base_salary(employee)
    amount = (
        round(body.amount_override, 2)
        if body.amount_override is not None
        else compute_tier_amount(tier, base_salary)
    )
    if amount <= 0:
        raise ValueError("Le montant de la prime doit être strictement positif")

    is_taxable = settings.default_is_taxable
    is_social = compute_social_tax_flag(
        amount,
        base_salary,
        body.payroll_year,
        settings.default_is_socially_taxed,
    )

    prime_data = MonthlyInputCreate(
        year=body.payroll_year,
        month=body.payroll_month,
        name=prime_label(tier),
        amount=amount,
        is_taxable=is_taxable,
        is_socially_taxed=is_social,
    )
    result = create_employee_monthly_input(case.employee_id, prime_data)
    inserted = result.inserted_data or {}
    monthly_input_id = inserted.get("id")

    now = datetime.now(timezone.utc).isoformat()
    row = work_medal_cases_repository.update(
        case_id,
        {
            "status": "paid",
            "amount_computed": amount,
            "payroll_year": body.payroll_year,
            "payroll_month": body.payroll_month,
            "monthly_input_id": monthly_input_id,
            "rh_validated_at": now,
            "rh_validated_by": rh_user_id,
        },
    )

    notify_employee_approved(
        case.employee_id,
        company_id,
        case.medal_level,
        amount,
        body.payroll_month,
        body.payroll_year,
    )
    return WorkMedalCase.model_validate(row)


def dismiss_work_medal_case(
    case_id: str,
    company_id: str,
    body: WorkMedalDismissRequest,
) -> WorkMedalCase:
    case = queries.get_work_medal_case(case_id)
    if not case or case.company_id != company_id:
        raise ValueError("Dossier introuvable")
    if case.status in ("approved", "paid"):
        raise ValueError("Impossible d'ignorer un dossier déjà validé ou payé")

    row = work_medal_cases_repository.update(
        case_id,
        {
            "status": "dismissed",
            "dismissed_reason": body.reason,
        },
    )
    return WorkMedalCase.model_validate(row)
