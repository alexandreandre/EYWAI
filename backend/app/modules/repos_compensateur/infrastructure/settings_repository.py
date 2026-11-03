"""
Repository paramètres contingent et ajustements salarié.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.core.database import supabase
from app.modules.repos_compensateur.domain.contingent_rules import (
    HOURS_PER_REST_DAY_DEFAULT,
    LEGAL_COR_CONTINGENT_DEFAULT,
    MANAGEMENT_CONTINGENT_DEFAULT,
    PAUSE_HS_DEDUCTION_PER_WORKDAY_DEFAULT,
    WORKDAYS_PER_YEAR_FOR_PAUSE_DEFAULT,
    ContingentSettings,
    contingent_legal_par_defaut,
)


def _idcc_de_la_societe(company_id: str) -> str | None:
    resp = (
        supabase.table("companies")
        .select("idcc")
        .eq("id", company_id)
        .limit(1)
        .execute()
    )
    rows = resp.data or []
    return rows[0].get("idcc") if rows else None


def _avec_contingent_de_la_convention(company_id: str, row: dict[str, Any]) -> dict[str, Any]:
    """Un contingent non saisi est celui de la convention (130 h en plasturgie)."""
    if row.get("legal_cor_contingent_hours") not in (None, ""):
        return row
    return {
        **row,
        "legal_cor_contingent_hours": contingent_legal_par_defaut(
            _idcc_de_la_societe(company_id)
        ),
    }


def _row_to_settings(row: dict[str, Any]) -> ContingentSettings:
    mgmt = row.get("management_contingent_hours")
    return ContingentSettings(
        legal_cor_contingent_hours=float(
            row.get("legal_cor_contingent_hours") or LEGAL_COR_CONTINGENT_DEFAULT
        ),
        management_contingent_hours=float(mgmt) if mgmt is not None else None,
        hours_per_rest_day=float(
            row.get("hours_per_rest_day") or HOURS_PER_REST_DAY_DEFAULT
        ),
        include_structural_hours=bool(row.get("include_structural_hours", True)),
        pause_deduction_enabled=bool(row.get("pause_deduction_enabled", False)),
        pause_hs_deduction_per_workday=float(
            row.get("pause_hs_deduction_per_workday")
            or PAUSE_HS_DEDUCTION_PER_WORKDAY_DEFAULT
        ),
        workdays_per_year_for_pause=int(
            row.get("workdays_per_year_for_pause")
            or WORKDAYS_PER_YEAR_FOR_PAUSE_DEFAULT
        ),
    )


def get_contingent_settings(company_id: str) -> ContingentSettings:
    """Lit les paramètres contingent ; retourne les defaults si absent."""
    resp = (
        supabase.table("company_overtime_contingent_settings")
        .select("*")
        .eq("company_id", company_id)
        .limit(1)
        .execute()
    )
    rows = resp.data or []
    if not rows:
        return ContingentSettings(
            legal_cor_contingent_hours=contingent_legal_par_defaut(
                _idcc_de_la_societe(company_id)
            ),
            management_contingent_hours=MANAGEMENT_CONTINGENT_DEFAULT,
        )
    return _row_to_settings(_avec_contingent_de_la_convention(company_id, rows[0]))


def get_contingent_settings_row(company_id: str) -> dict[str, Any]:
    """Lit la ligne settings brute (pour API GET)."""
    resp = (
        supabase.table("company_overtime_contingent_settings")
        .select("*")
        .eq("company_id", company_id)
        .limit(1)
        .execute()
    )
    rows = resp.data or []
    if not rows:
        return {
            "company_id": company_id,
            "legal_cor_contingent_hours": contingent_legal_par_defaut(
                _idcc_de_la_societe(company_id)
            ),
            "management_contingent_hours": MANAGEMENT_CONTINGENT_DEFAULT,
            "hours_per_rest_day": HOURS_PER_REST_DAY_DEFAULT,
            "include_structural_hours": True,
            "pause_deduction_enabled": False,
            "pause_hs_deduction_per_workday": PAUSE_HS_DEDUCTION_PER_WORKDAY_DEFAULT,
            "workdays_per_year_for_pause": WORKDAYS_PER_YEAR_FOR_PAUSE_DEFAULT,
        }
    return _avec_contingent_de_la_convention(company_id, rows[0])


def upsert_contingent_settings(company_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Crée ou met à jour les paramètres contingent entreprise."""
    now = datetime.now(timezone.utc).isoformat()
    row = {
        "company_id": company_id,
        "updated_at": now,
    }
    allowed = (
        "legal_cor_contingent_hours",
        "management_contingent_hours",
        "hours_per_rest_day",
        "include_structural_hours",
        "pause_deduction_enabled",
        "pause_hs_deduction_per_workday",
        "workdays_per_year_for_pause",
    )
    for key in allowed:
        if key in payload:
            row[key] = payload[key]

    existing = (
        supabase.table("company_overtime_contingent_settings")
        .select("id")
        .eq("company_id", company_id)
        .limit(1)
        .execute()
    )
    if existing.data:
        supabase.table("company_overtime_contingent_settings").update(row).eq(
            "company_id", company_id
        ).execute()
    else:
        row["created_at"] = now
        # La colonne a 220 par défaut en base : sans ce champ, la plasturgie
        # serait créée à 220 h au lieu de ses 130 h.
        row = _avec_contingent_de_la_convention(company_id, row)
        supabase.table("company_overtime_contingent_settings").insert(row).execute()

    return get_contingent_settings_row(company_id)


def get_adjustments_by_company_year(
    company_id: str, year: int
) -> dict[str, float]:
    """Map employee_id -> opening_balance_hours."""
    resp = (
        supabase.table("employee_overtime_adjustments")
        .select("employee_id, opening_balance_hours")
        .eq("company_id", company_id)
        .eq("year", year)
        .execute()
    )
    result: dict[str, float] = {}
    for row in resp.data or []:
        eid = str(row["employee_id"])
        result[eid] = float(row.get("opening_balance_hours") or 0)
    return result


def get_adjustment(
    company_id: str, employee_id: str, year: int
) -> dict[str, Any] | None:
    resp = (
        supabase.table("employee_overtime_adjustments")
        .select("*")
        .eq("company_id", company_id)
        .eq("employee_id", employee_id)
        .eq("year", year)
        .limit(1)
        .execute()
    )
    rows = resp.data or []
    return rows[0] if rows else None


def upsert_adjustment(
    company_id: str,
    employee_id: str,
    year: int,
    opening_balance_hours: float,
    note: str | None = None,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    existing = get_adjustment(company_id, employee_id, year)
    row = {
        "company_id": company_id,
        "employee_id": employee_id,
        "year": year,
        "opening_balance_hours": opening_balance_hours,
        "note": note,
        "updated_at": now,
    }
    if existing:
        supabase.table("employee_overtime_adjustments").update(row).eq(
            "id", existing["id"]
        ).execute()
    else:
        row["created_at"] = now
        supabase.table("employee_overtime_adjustments").insert(row).execute()
    result = get_adjustment(company_id, employee_id, year)
    return result or row
