"""Enrichissement et contrôle du verrouillage d'édition manuelle des bulletins."""

from __future__ import annotations

from datetime import date
from typing import Any

from app.modules.payslips.domain.period_edit_lock import (
    is_payslip_manual_edit_allowed,
    manual_edit_allowed_until,
    payslip_manual_edit_block_reason,
)
from app.modules.payslips.infrastructure.payslip_edit_lock_config import (
    get_cutoff_day_of_next_month,
)


def enrich_payslip_detail_with_edit_lock(
    detail: dict[str, Any],
    *,
    bypass_lock: bool = False,
    today: date | None = None,
    cutoff_day: int | None = None,
) -> dict[str, Any]:
    """Ajoute manual_edit_locked, manual_edit_lock_reason, manual_edit_lock_until."""
    out = dict(detail)
    try:
        year = int(detail.get("year") or 0)
        month = int(detail.get("month") or 0)
    except (TypeError, ValueError):
        year, month = 0, 0
    if year <= 0 or not (1 <= month <= 12):
        out["period_edit_locked"] = False
        out["manual_edit_locked"] = False
        out["manual_edit_lock_reason"] = None
        out["manual_edit_lock_until"] = None
        return out

    cutoff = cutoff_day if cutoff_day is not None else get_cutoff_day_of_next_month()
    period_locked = not is_payslip_manual_edit_allowed(
        year, month, cutoff_day=cutoff, today=today
    )
    locked_for_user = period_locked and not bypass_lock
    out["period_edit_locked"] = period_locked
    out["manual_edit_locked"] = locked_for_user
    out["manual_edit_lock_reason"] = (
        payslip_manual_edit_block_reason(
            year, month, cutoff_day=cutoff, today=today
        )
        if locked_for_user
        else None
    )
    allowed_until = manual_edit_allowed_until(year, month, cutoff)
    out["manual_edit_lock_until"] = (
        None if period_locked else allowed_until.isoformat()
    )
    return out


def assert_payslip_manual_edit_allowed(
    meta: dict[str, Any],
    *,
    bypass_lock: bool = False,
    today: date | None = None,
    cutoff_day: int | None = None,
) -> None:
    """Lève ValueError si l'édition manuelle est verrouillée pour la période."""
    if bypass_lock:
        return
    try:
        year = int(meta.get("year") or 0)
        month = int(meta.get("month") or 0)
    except (TypeError, ValueError):
        return
    if year <= 0 or not (1 <= month <= 12):
        return
    cutoff = cutoff_day if cutoff_day is not None else get_cutoff_day_of_next_month()
    reason = payslip_manual_edit_block_reason(
        year, month, cutoff_day=cutoff, today=today
    )
    if reason:
        raise ValueError(reason)
