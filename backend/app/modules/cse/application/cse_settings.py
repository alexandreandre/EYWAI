"""Lecture / écriture paramètres CSE entreprise."""

from __future__ import annotations

from typing import Any, Dict, Optional

from app.modules.cse.infrastructure.cse_settings_repository import cse_settings_repository
from app.modules.cse.schemas.responses import CompanyCseSettings

_WRITABLE_KEYS = frozenset(
    {
        "cse_status",
        "carence_pv_document_id",
        "carence_valid_until",
        "notes",
    }
)

_VALID_STATUSES = frozenset(
    {"unknown", "not_required", "obligation_pending", "carence", "elected"}
)


def _defaults(company_id: str) -> CompanyCseSettings:
    return CompanyCseSettings(
        company_id=company_id,
        cse_status="unknown",
        carence_pv_document_id=None,
        carence_valid_until=None,
        notes=None,
    )


def get_company_cse_settings(company_id: str) -> CompanyCseSettings:
    row = cse_settings_repository.get_by_company(company_id)
    if not row:
        return _defaults(company_id)
    return CompanyCseSettings.model_validate(row)


def save_company_cse_settings(
    company_id: str, patch: Dict[str, Any]
) -> CompanyCseSettings:
    current = get_company_cse_settings(company_id)
    merged = current.model_dump(mode="json")
    filtered = {k: v for k, v in patch.items() if k in _WRITABLE_KEYS}
    if "cse_status" in filtered:
        status = str(filtered["cse_status"] or "unknown")
        if status not in _VALID_STATUSES:
            raise ValueError(f"cse_status invalide : {status}")
        filtered["cse_status"] = status
    merged.update(filtered)
    payload = {k: merged[k] for k in _WRITABLE_KEYS if k in merged}
    row = cse_settings_repository.upsert(company_id, payload)
    return CompanyCseSettings.model_validate(row)


def count_active_elected_members(company_id: str) -> int:
    from app.core.database import supabase

    r = (
        supabase.table("cse_elected_members")
        .select("id", count="exact")
        .eq("company_id", company_id)
        .eq("is_active", True)
        .execute()
    )
    return int(r.count or 0)
