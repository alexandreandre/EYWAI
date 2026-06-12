"""CRUD des mappings comptables PCG paie (override société)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.core.database import supabase

from app.modules.exports.schemas.accounting_mappings import (
    AccountingMappingOut,
    AccountingMappingUpsert,
    AccountingMappingsListResponse,
)


def _row_to_out(row: Dict[str, Any]) -> AccountingMappingOut:
    return AccountingMappingOut(
        id=str(row["id"]),
        company_id=str(row["company_id"]) if row.get("company_id") else None,
        rubrique_code=row["rubrique_code"],
        rubrique_libelle=row["rubrique_libelle"],
        compte_comptable=row["compte_comptable"],
        journal=row.get("journal", "OD"),
        sens=row.get("sens", "debit"),
        type_rubrique=row.get("type_rubrique", "salaire"),
        analytique=row.get("analytique"),
        is_active=bool(row.get("is_active", True)),
        is_global_default=row.get("company_id") is None,
    )


def list_accounting_mappings(company_id: str) -> AccountingMappingsListResponse:
    global_r = (
        supabase.table("accounting_mappings")
        .select("*")
        .is_("company_id", "null")
        .eq("is_active", True)
        .execute()
    )
    company_r = (
        supabase.table("accounting_mappings")
        .select("*")
        .eq("company_id", company_id)
        .execute()
    )
    globals_list = global_r.data or []
    company_list = company_r.data or []
    by_code: Dict[str, Dict[str, Any]] = {
        row["rubrique_code"]: row for row in globals_list
    }
    for row in company_list:
        by_code[row["rubrique_code"]] = row

    mappings = [_row_to_out(row) for row in sorted(by_code.values(), key=lambda r: r["rubrique_code"])]
    return AccountingMappingsListResponse(
        mappings=mappings,
        company_overrides_count=len(company_list),
    )


def upsert_company_mapping(
    company_id: str, body: AccountingMappingUpsert
) -> AccountingMappingOut:
    payload = {
        "company_id": company_id,
        "rubrique_code": body.rubrique_code,
        "rubrique_libelle": body.rubrique_libelle,
        "compte_comptable": body.compte_comptable,
        "journal": body.journal,
        "sens": body.sens,
        "type_rubrique": body.type_rubrique,
        "analytique": body.analytique,
        "is_active": body.is_active,
    }
    existing = (
        supabase.table("accounting_mappings")
        .select("id")
        .eq("company_id", company_id)
        .eq("rubrique_code", body.rubrique_code)
        .maybe_single()
        .execute()
    )
    if existing and existing.data:
        up = (
            supabase.table("accounting_mappings")
            .update(payload)
            .eq("id", existing.data["id"])
            .execute()
        )
        row = up.data[0] if isinstance(up.data, list) else up.data
    else:
        ins = supabase.table("accounting_mappings").insert(payload).execute()
        row = ins.data[0] if isinstance(ins.data, list) else ins.data
    return _row_to_out(row)


def delete_company_mapping(company_id: str, rubrique_code: str) -> None:
    supabase.table("accounting_mappings").delete().eq(
        "company_id", company_id
    ).eq("rubrique_code", rubrique_code).execute()
