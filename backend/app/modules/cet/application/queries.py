"""Requêtes CET — soldes CP pour transferts et intégration absences."""

from __future__ import annotations

from datetime import date
from typing import Any

from app.core.database import supabase
from app.modules.absences.application.queries import (
    _leave_context,
    _parse_hire_date,
)
from app.modules.absences.domain.rules import get_available_conge_paye_days
from app.modules.absences.infrastructure.repository import absence_repository
from app.modules.cet.domain.rules import (
    CetMovementRow,
    compute_cp_days_committed_for_absences,
    convert_cp_days_between_units,
    HOURS_PER_REST_DAY_DEFAULT,
    OUVRES_TO_OUVRABLES_DEFAULT,
)
from app.modules.cet.infrastructure import repository as cet_repo


def _movement_rows(raw: list[dict[str, Any]]) -> list[CetMovementRow]:
    return [
        CetMovementRow(
            movement_type=str(m["movement_type"]),
            hours=float(m.get("hours") or 0),
            status=str(m.get("status") or ""),
            days=float(m.get("days") or 0),
            year=int(m.get("year") or 0),
        )
        for m in raw
    ]


def _get_employee_company_id(employee_id: str) -> str | None:
    resp = (
        supabase.table("employees")
        .select("company_id")
        .eq("id", employee_id)
        .limit(1)
        .execute()
    )
    rows = resp.data or []
    return str(rows[0]["company_id"]) if rows else None


def _read_settings(company_id: str) -> dict[str, Any]:
    row = cet_repo.get_cet_settings_row(company_id)
    return {
        "cet_enabled": bool(row.get("cet_enabled")),
        "allow_deposit_cp": bool(row.get("allow_deposit_cp")),
        "cp_unit": row.get("cp_unit") or "ouvrables",
        "ouvres_to_ouvrables_ratio": float(
            row.get("ouvres_to_ouvrables_ratio") or OUVRES_TO_OUVRABLES_DEFAULT
        ),
        "cp_debit_timing": row.get("cp_debit_timing") or "on_validation",
        "hours_per_rest_day": float(row.get("hours_per_rest_day") or HOURS_PER_REST_DAY_DEFAULT),
    }


def get_cet_cp_committed_days(
    employee_id: str,
    year: int,
    *,
    company_id: str | None = None,
) -> float:
    """Jours CP engagés via CET (selon timing débit entreprise), en unité accord CET."""
    emp_company = company_id or _get_employee_company_id(employee_id)
    if not emp_company:
        return 0.0
    settings = _read_settings(emp_company)
    movements = cet_repo.list_movements_for_employee(employee_id, year=year)
    rows = _movement_rows(movements)
    return compute_cp_days_committed_for_absences(
        rows,
        year,
        cp_debit_timing=settings["cp_debit_timing"],
    )


def get_cp_balance_available_for_cet(
    employee_id: str,
    ref_date: date | None = None,
) -> float:
    """
    Solde CP disponible pour un transfert CET, dans l'unité paramétrée (ouvres/ouvrables).
    """
    ref = ref_date or date.today()
    hire_date = _parse_hire_date(employee_id)
    if not hire_date:
        return 0.0

    company_id = _get_employee_company_id(employee_id)
    if not company_id:
        return 0.0
    settings = _read_settings(company_id)
    if not settings["allow_deposit_cp"]:
        return 0.0

    cp_unit = settings["cp_unit"]
    ratio = settings["ouvres_to_ouvrables_ratio"]
    requests = absence_repository.list_by_employee_id(employee_id)
    policy, adjustment, _, cp_seniority = _leave_context(employee_id, ref.year, company_id)
    from app.modules.absences.application.queries import _cp_balance_extras

    extras = _cp_balance_extras(employee_id, ref, company_id, policy, cp_seniority)
    raw_available = get_available_conge_paye_days(
        hire_date,
        requests,
        ref,
        policy=policy,
        adjustment=adjustment,
        **extras,
    )
    available_in_cet_unit = convert_cp_days_between_units(
        raw_available,
        "ouvrables",
        cp_unit,
        ratio,
    )
    cet_committed = get_cet_cp_committed_days(
        employee_id, ref.year, company_id=company_id
    )
    return round(max(0.0, available_in_cet_unit - cet_committed), 2)


def get_cet_cp_extra_committed_for_absences(
    employee_id: str,
    year: int,
) -> float:
    """Jours CP CET à soustraire du solde absences (unité ouvrables)."""
    company_id = _get_employee_company_id(employee_id)
    if not company_id:
        return 0.0
    settings = _read_settings(company_id)
    if not settings["cet_enabled"] or not settings["allow_deposit_cp"]:
        return 0.0

    cp_unit = settings["cp_unit"]
    ratio = settings["ouvres_to_ouvrables_ratio"]
    movements = cet_repo.list_movements_for_employee(employee_id, year=year)
    rows = _movement_rows(movements)
    committed_cet_unit = compute_cp_days_committed_for_absences(
        rows,
        year,
        cp_debit_timing=settings["cp_debit_timing"],
    )
    return convert_cp_days_between_units(
        committed_cet_unit,
        cp_unit,
        "ouvrables",
        ratio,
    )
