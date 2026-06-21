"""Prime astreinte hebdomadaire — paliers Noël / pont (domaine pur)."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from app.modules.payroll_variables.domain.astreinte_km import astreinte_week_mondays


def _default_conditions(conditions: dict[str, Any] | None) -> dict[str, Any]:
    c = dict(conditions or {})
    return {
        "amount_normal": float(c.get("amount_normal") or c.get("amount") or 0),
        "amount_christmas": float(c.get("amount_christmas") or 0),
        "amount_bridge": float(c.get("amount_bridge") or 0),
        "christmas_mode": str(c.get("christmas_mode") or "replace"),
        "bridge_mode": str(c.get("bridge_mode") or "add"),
        "christmas_detection": str(c.get("christmas_detection") or "iso_dec_25"),
        "bridge_requires_astreinte_on_day": bool(
            c.get("bridge_requires_astreinte_on_day", True)
        ),
    }


def astreinte_weeks_in_period(shift_dates: list[date]) -> set[date]:
    """Lundis ISO des semaines contenant au moins une astreinte."""
    return astreinte_week_mondays(shift_dates)


def _week_range(monday: date) -> tuple[date, date]:
    return monday, monday + timedelta(days=6)


def _date_in_range(d: date, start: date, end: date) -> bool:
    return start <= d <= end


def is_christmas_week(
    monday: date,
    *,
    detection: str,
    special_days: list[dict[str, Any]],
    year: int,
) -> bool:
    week_start, week_end = _week_range(monday)
    if detection == "special_day_tag":
        for row in special_days:
            if row.get("kind") != "christmas_week":
                continue
            raw = row.get("day_date")
            if not raw:
                continue
            d = date.fromisoformat(str(raw)[:10])
            if _date_in_range(d, week_start, week_end):
                return True
        return False
    for offset in range(7):
        d = week_start + timedelta(days=offset)
        if d.month == 12 and d.day == 25:
            return True
    return False


def week_bridge_dates(
    monday: date,
    shift_dates: list[date],
    bridge_dates: list[date],
    *,
    requires_astreinte_on_day: bool,
) -> list[date]:
    week_start, week_end = _week_range(monday)
    astreinte_set = set(shift_dates)
    qualifying: list[date] = []
    for bridge in bridge_dates:
        if not _date_in_range(bridge, week_start, week_end):
            continue
        if requires_astreinte_on_day and bridge not in astreinte_set:
            continue
        qualifying.append(bridge)
    return qualifying


def compute_week_payouts(
    monday: date,
    shift_dates: list[date],
    bridge_dates: list[date],
    special_days: list[dict[str, Any]],
    conditions: dict[str, Any] | None,
    *,
    year: int,
) -> list[dict[str, Any]]:
    """
    Retourne une liste de lignes {kind, amount, label, monday, details}.
    """
    cfg = _default_conditions(conditions)
    if cfg["amount_normal"] <= 0 and cfg["amount_christmas"] <= 0:
        return []

    christmas = is_christmas_week(
        monday,
        detection=cfg["christmas_detection"],
        special_days=special_days,
        year=year,
    )
    bridges = week_bridge_dates(
        monday,
        shift_dates,
        bridge_dates,
        requires_astreinte_on_day=cfg["bridge_requires_astreinte_on_day"],
    )

    lines: list[dict[str, Any]] = []
    week_amount = cfg["amount_normal"]
    week_kind = "week_normal"

    if christmas:
        if cfg["christmas_mode"] == "add":
            week_amount = cfg["amount_normal"] + cfg["amount_christmas"]
            week_kind = "week_christmas_add"
        else:
            week_amount = cfg["amount_christmas"] or cfg["amount_normal"]
            week_kind = "week_christmas_replace"

    if week_amount > 0:
        lines.append(
            {
                "kind": week_kind,
                "amount": round(week_amount, 2),
                "label": "Prime astreinte semaine",
                "monday": monday.isoformat(),
                "quantity": 1.0,
                "details": {"christmas": christmas, "monday": monday.isoformat()},
            }
        )

    if bridges and cfg["amount_bridge"] > 0:
        bridge_amount = cfg["amount_bridge"]
        if cfg["bridge_mode"] == "replace" and len(lines) == 1:
            lines = [
                {
                    "kind": "week_bridge_replace",
                    "amount": round(bridge_amount, 2),
                    "label": "Prime astreinte pont",
                    "monday": monday.isoformat(),
                    "quantity": 1.0,
                    "details": {
                        "bridge_dates": [b.isoformat() for b in bridges],
                        "monday": monday.isoformat(),
                    },
                }
            ]
        else:
            lines.append(
                {
                    "kind": "week_bridge_add",
                    "amount": round(bridge_amount, 2),
                    "label": "Prime astreinte pont",
                    "monday": monday.isoformat(),
                    "quantity": 1.0,
                    "details": {
                        "bridge_dates": [b.isoformat() for b in bridges],
                        "monday": monday.isoformat(),
                    },
                }
            )

    return lines


def evaluate_astreinte_week_tiered(
    rule: dict[str, Any],
    *,
    year: int,
    month: int,
    shift_dates: list[date],
    special_days: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Évalue une règle per_astreinte_week_tiered pour un mois."""
    conditions = rule.get("conditions") or {}
    mondays = astreinte_weeks_in_period(shift_dates)
    bridge_dates = [
        date.fromisoformat(str(r["day_date"])[:10])
        for r in special_days
        if r.get("kind") == "bridge" and r.get("day_date")
    ]

    month_start = date(year, month, 1)
    if month < 12:
        month_end = date(year, month + 1, 1) - timedelta(days=1)
    else:
        month_end = date(year, 12, 31)

    results: list[dict[str, Any]] = []
    for monday in sorted(mondays):
        week_end = monday + timedelta(days=6)
        if week_end < month_start or monday > month_end:
            continue
        week_shifts = [d for d in shift_dates if monday <= d <= week_end]
        payouts = compute_week_payouts(
            monday,
            week_shifts,
            bridge_dates,
            special_days,
            conditions,
            year=year,
        )
        for payout in payouts:
            payout["rule_code"] = rule.get("code")
            results.append(payout)
    return results
