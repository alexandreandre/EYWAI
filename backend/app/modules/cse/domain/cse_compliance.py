"""Règles conformité CSE (carence électorale vs obligation légale)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, Optional


def _parse_date(value: Any) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    raw = str(value)[:10]
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def resolve_cse_status_label(status: str, *, carence_expired: bool = False) -> str:
    if status == "carence" and carence_expired:
        return "carence_expired"
    return status


def compute_cse_compliance(
    headcount: int,
    *,
    cse_settings: Optional[Dict[str, Any]] = None,
    active_elected_count: int = 0,
    today: Optional[date] = None,
) -> Dict[str, Any]:
    """
    Détermine si l'entreprise est conforme côté CSE.

    - effectif < 11 : not_required, ok
    - élus actifs > 0 : elected, ok
    - carence avec PV valide (carence_valid_until >= today) : ok
    - sinon : obligation_pending ou carence expirée, non ok
    """
    ref = today or date.today()
    settings = cse_settings or {}
    configured_status = str(settings.get("cse_status") or "unknown").strip()
    valid_until = _parse_date(settings.get("carence_valid_until"))

    if headcount < 11:
        return {
            "cse_obligation": False,
            "cse_ok": True,
            "cse_status": "not_required",
            "carence_valid_until": valid_until.isoformat() if valid_until else None,
            "carence_expired": False,
        }

    if active_elected_count > 0:
        return {
            "cse_obligation": True,
            "cse_ok": True,
            "cse_status": "elected",
            "carence_valid_until": valid_until.isoformat() if valid_until else None,
            "carence_expired": False,
        }

    if configured_status == "carence":
        expired = valid_until is None or valid_until < ref
        return {
            "cse_obligation": True,
            "cse_ok": not expired,
            "cse_status": "carence_expired" if expired else "carence",
            "carence_valid_until": valid_until.isoformat() if valid_until else None,
            "carence_expired": expired,
        }

    status = configured_status if configured_status != "unknown" else "obligation_pending"
    return {
        "cse_obligation": True,
        "cse_ok": False,
        "cse_status": status,
        "carence_valid_until": valid_until.isoformat() if valid_until else None,
        "carence_expired": False,
    }
