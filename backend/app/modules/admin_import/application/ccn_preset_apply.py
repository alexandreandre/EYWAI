"""Application des presets CCN pour onboarding entreprise."""

from __future__ import annotations

from typing import Any, Dict

from app.core.database import get_supabase_admin_client
from app.modules.absences.domain.ccn_setup_presets import (
    get_leave_preset_for_idcc,
    get_modulation_preset_for_idcc,
    normalize_idcc,
)
from app.modules.absences.infrastructure.leave_settings_repository import upsert_leave_policy
from app.modules.admin_import.infrastructure import repository as repo


def _db():
    return get_supabase_admin_client()


def apply_ccn_setup_presets(company_id: str) -> Dict[str, Any]:
    company = repo.find_company(company_id)
    if not company:
        raise LookupError("Entreprise introuvable.")

    idcc = normalize_idcc(company.get("idcc"))
    leave_preset = get_leave_preset_for_idcc(idcc)
    modulation_preset = get_modulation_preset_for_idcc(idcc)

    upsert_leave_policy(company_id, leave_preset)

    mod_resp = (
        _db()
        .table("company_modulation_settings")
        .select("id")
        .eq("company_id", company_id)
        .limit(1)
        .execute()
    )
    rows = mod_resp.data or []
    if rows:
        _db().table("company_modulation_settings").update(modulation_preset).eq(
            "company_id", company_id
        ).execute()
    else:
        payload = {"company_id": company_id, **modulation_preset}
        _db().table("company_modulation_settings").insert(payload).execute()

    return {
        "company_id": company_id,
        "idcc": idcc or None,
        "leave_preset_applied": True,
        "modulation_preset_applied": True,
    }
