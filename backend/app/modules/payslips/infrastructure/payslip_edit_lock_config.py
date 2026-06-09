"""Lecture de la configuration globale de verrouillage d'édition des bulletins."""

from __future__ import annotations

from typing import Any

from app.core.database import supabase
from app.modules.payslips.domain.period_edit_lock import (
    DEFAULT_CUTOFF_DAY,
    normalize_cutoff_day,
)
from app.modules.payroll.engine.baremes_loader import ensure_dict

CONFIG_KEY = "payslip_edit_lock"


def get_payslip_edit_lock_config() -> dict[str, Any]:
    """Retourne la config active (cutoff_day_of_next_month)."""
    try:
        response = (
            supabase.table("payroll_config")
            .select("config_data")
            .eq("config_key", CONFIG_KEY)
            .eq("is_active", True)
            .is_("company_id", "null")
            .order("version", desc=True)
            .limit(1)
            .execute()
        )
        rows = response.data or []
        if rows:
            data = ensure_dict(rows[0].get("config_data"))
            cutoff = normalize_cutoff_day(data.get("cutoff_day_of_next_month"))
            return {"cutoff_day_of_next_month": cutoff}
    except Exception:
        pass
    return {"cutoff_day_of_next_month": DEFAULT_CUTOFF_DAY}


def get_cutoff_day_of_next_month() -> int:
    return int(get_payslip_edit_lock_config()["cutoff_day_of_next_month"])
