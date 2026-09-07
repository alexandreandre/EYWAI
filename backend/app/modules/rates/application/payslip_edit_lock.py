"""Configuration admin du verrouillage d'édition manuelle des bulletins."""

from __future__ import annotations

from typing import Any

from app.modules.payslips.domain.period_edit_lock import normalize_cutoff_day
from app.modules.payslips.infrastructure.payslip_edit_lock_config import (
    CONFIG_KEY,
    get_payslip_edit_lock_config,
)
from app.modules.rates.application.manual import apply_manual_rate_override
from app.modules.rates.domain.interfaces import IRatesWriter


def get_payslip_edit_lock_settings() -> dict[str, Any]:
    return get_payslip_edit_lock_config()


def save_payslip_edit_lock_settings(
    writer: IRatesWriter,
    *,
    cutoff_day_of_next_month: int,
    actor_label: str,
    comment: str | None = None,
    enabled: bool = True,
) -> dict[str, Any]:
    cutoff = normalize_cutoff_day(cutoff_day_of_next_month)
    config_data = {"cutoff_day_of_next_month": cutoff, "enabled": bool(enabled)}
    result = apply_manual_rate_override(
        writer,
        config_key=CONFIG_KEY,
        config_data=config_data,
        actor_label=actor_label,
        comment=comment,
    )
    return {"cutoff_day_of_next_month": cutoff, "enabled": bool(enabled), **result}
