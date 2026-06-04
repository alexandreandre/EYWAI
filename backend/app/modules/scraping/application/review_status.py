"""
Filtrage des validations / alertes scraping déjà traitées.

Masque les changements en attente et les alertes « review_required » lorsque le
dernier taux scrapé correspond déjà à la config active (validation manuelle,
approbation ou re-scrape identique).
"""

from __future__ import annotations

import copy
from typing import Any


def _strip_cotisation_check_timestamps(config_data: dict[str, Any]) -> dict[str, Any]:
    data = copy.deepcopy(config_data)
    for item in data.get("cotisations", []):
        if isinstance(item, dict):
            item.pop("last_checked_at", None)
    return data


def config_data_matches(
    *,
    persistence_mode: str,
    current_data: dict[str, Any] | None,
    proposed_data: dict[str, Any] | None,
) -> bool:
    """True si la proposition est déjà reflétée dans la config active."""
    if proposed_data is None:
        return False
    current = current_data or {}
    if persistence_mode == "cotisations":
        return _strip_cotisation_check_timestamps(current) == _strip_cotisation_check_timestamps(
            proposed_data
        )
    return current == proposed_data


def pending_requires_action(
    pending: dict[str, Any],
    active_config_row: dict[str, Any] | None,
) -> bool:
    """False si le changement en attente n'a plus rien à appliquer."""
    proposed = pending.get("proposed_config_data")
    if not isinstance(proposed, dict):
        return True
    current_data = (active_config_row or {}).get("config_data")
    if not isinstance(current_data, dict):
        return True
    persistence_mode = pending.get("persistence_mode") or "full"
    return not config_data_matches(
        persistence_mode=persistence_mode,
        current_data=current_data,
        proposed_data=proposed,
    )


def _parse_ts(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _is_after(left: Any, right: Any) -> bool:
    left_ts = _parse_ts(left)
    right_ts = _parse_ts(right)
    if not left_ts or not right_ts:
        return False
    return left_ts > right_ts


def review_alert_requires_action(
    alert: dict[str, Any],
    *,
    pending_rows: list[dict[str, Any]],
    active_configs: dict[str, dict[str, Any]],
    latest_approved: dict[str, dict[str, Any]],
) -> bool:
    """False si l'alerte review_required ne correspond plus à un taux problématique."""
    if alert.get("alert_type") != "review_required":
        return True

    details = alert.get("details") or {}
    config_key = details.get("config_key")
    if not config_key:
        return True

    related_pending = [
        row
        for row in pending_rows
        if row.get("config_key") == config_key and row.get("status") == "pending"
    ]
    for pending in related_pending:
        if pending_requires_action(pending, active_configs.get(config_key)):
            return True

    approved = latest_approved.get(config_key)
    if approved and _is_after(
        approved.get("applied_at") or approved.get("reviewed_at"),
        alert.get("created_at"),
    ):
        return False

    if related_pending:
        return False

    return True


def filter_actionable_pending(
    pending_rows: list[dict[str, Any]],
    active_configs: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    return [
        row
        for row in pending_rows
        if row.get("status") != "pending"
        or pending_requires_action(row, active_configs.get(row.get("config_key", "")))
    ]


def filter_actionable_alerts(
    alerts: list[dict[str, Any]],
    *,
    pending_rows: list[dict[str, Any]],
    active_configs: dict[str, dict[str, Any]],
    latest_approved: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    return [
        alert
        for alert in alerts
        if review_alert_requires_action(
            alert,
            pending_rows=pending_rows,
            active_configs=active_configs,
            latest_approved=latest_approved,
        )
    ]


def load_active_configs_by_key(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {row["config_key"]: row for row in rows if row.get("config_key")}
