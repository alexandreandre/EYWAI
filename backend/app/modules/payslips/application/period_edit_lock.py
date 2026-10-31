"""Enrichissement et contrôle du verrouillage d'édition manuelle des bulletins."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from app.modules.payslips.domain.mise_a_disposition import (
    message_bulletin_remis,
    message_pas_encore_disponible,
    remis_le_du_bulletin,
)
from app.modules.payslips.domain.period_edit_lock import (
    is_payslip_manual_edit_allowed,
    manual_edit_allowed_until,
    payslip_manual_edit_block_reason,
)
from app.modules.payslips.infrastructure.mise_a_disposition_queries import jour_de_la_societe
from app.modules.payslips.infrastructure.payslip_edit_lock_config import (
    get_payslip_edit_lock_config,
)
from app.shared.domain.temps_local import aujourd_hui_local


def _resolve_lock_settings(
    cutoff_day: int | None, lock_enabled: bool | None
) -> tuple[int, bool]:
    """(cutoff, enabled) — une seule lecture de config quand un champ manque."""
    if cutoff_day is not None and lock_enabled is not None:
        return cutoff_day, lock_enabled
    config = get_payslip_edit_lock_config()
    return (
        cutoff_day if cutoff_day is not None else int(config["cutoff_day_of_next_month"]),
        lock_enabled if lock_enabled is not None else bool(config["enabled"]),
    )


def _remise(bulletin: dict[str, Any], jour_remise: int | None) -> date | None:
    """Jour où le salarié reçoit ce bulletin validé (D5) ; None sinon."""
    if str(bulletin.get("status") or "") != "valide":
        return None
    jour = jour_remise if jour_remise is not None else jour_de_la_societe(bulletin.get("company_id"))
    try:
        return remis_le_du_bulletin(bulletin, jour=jour)
    except (KeyError, TypeError, ValueError):
        return None


def refus_avant_remise(bulletin: dict[str, Any], *, today: date | None = None) -> str | None:
    """Pour le salarié : la phrase qui refuse un bulletin pas encore remis ; None
    s'il l'est."""
    remis = _remise(bulletin, None)
    if remis and remis <= (today or aujourd_hui_local()):
        return None
    return message_pas_encore_disponible(remis)


def enrich_payslip_detail_with_edit_lock(
    detail: dict[str, Any],
    *,
    bypass_lock: bool = False,
    today: date | None = None,
    cutoff_day: int | None = None,
    lock_enabled: bool | None = None,
    jour_remise: int | None = None,
) -> dict[str, Any]:
    """Ajoute manual_edit_locked, manual_edit_lock_reason, manual_edit_lock_until,
    et la remise au salarié (remis_le, bulletin_remis)."""
    out = dict(detail)
    out["remis_le"] = None
    out["bulletin_remis"] = False
    if str(detail.get("origine") or "") == "importe":
        # Bulletin repris à la bascule : intouchable, sans contournement admin —
        # il ne pourrait pas être recalculé (cf. commands.MESSAGE_BULLETIN_IMPORTE).
        from app.modules.payslips.application.commands import MESSAGE_BULLETIN_IMPORTE

        out["period_edit_locked"] = True
        out["manual_edit_locked"] = True
        out["manual_edit_lock_reason"] = MESSAGE_BULLETIN_IMPORTE
        out["manual_edit_lock_until"] = None
        return out
    remis = _remise(detail, jour_remise)
    out["remis_le"] = remis.isoformat() if remis else None
    if remis and remis <= (today or aujourd_hui_local()):
        # D4 : remis au salarié, il ne se modifie plus ; l'erreur se corrige
        # le mois suivant. Le verrou de période ne le rouvre pas.
        out["bulletin_remis"] = True
        out["period_edit_locked"] = True
        out["manual_edit_locked"] = not bypass_lock
        out["manual_edit_lock_reason"] = (
            None
            if bypass_lock
            else message_bulletin_remis(int(detail["year"]), int(detail["month"]), remis)
        )
        out["manual_edit_lock_until"] = None
        return out
    cutoff, enabled = _resolve_lock_settings(cutoff_day, lock_enabled)
    if not enabled:
        # Verrou désactivé globalement (réglage admin) : l'édition manuelle
        # reste ouverte sans limite de date.
        out["period_edit_locked"] = False
        out["manual_edit_locked"] = False
        out["manual_edit_lock_reason"] = None
        out["manual_edit_lock_until"] = None
        return out
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
    if remis:
        # Validé, pas encore remis : il se fige à sa remise, souvent avant le 15.
        allowed_until = min(allowed_until, remis - timedelta(days=1))
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
    lock_enabled: bool | None = None,
    jour_remise: int | None = None,
) -> None:
    """Lève ValueError si le bulletin est remis au salarié (D4) ou si l'édition
    manuelle est verrouillée pour la période."""
    if bypass_lock:
        return
    try:
        year = int(meta.get("year") or 0)
        month = int(meta.get("month") or 0)
    except (TypeError, ValueError):
        return
    if year <= 0 or not (1 <= month <= 12):
        return
    remis = _remise(meta, jour_remise)
    if remis and remis <= (today or aujourd_hui_local()):
        raise ValueError(message_bulletin_remis(year, month, remis))
    cutoff, enabled = _resolve_lock_settings(cutoff_day, lock_enabled)
    if not enabled:
        return
    reason = payslip_manual_edit_block_reason(
        year, month, cutoff_day=cutoff, today=today
    )
    if reason:
        raise ValueError(reason)
