"""Majorations astreinte week-end — 1 h forfait samedi/dimanche (domaine pur)."""

from __future__ import annotations

from datetime import date
from typing import Any

from app.modules.payroll_variables.domain.astreinte_km import (
    astreinte_week_mondays,
    weekend_work_days,
)


def _default_conditions(conditions: dict[str, Any] | None) -> dict[str, Any]:
    c = dict(conditions or {})
    raw_rates = c.get("weekday_rates") or {"5": 0.25, "6": 1.0}
    weekday_rates: dict[int, float] = {}
    if isinstance(raw_rates, dict):
        for key, val in raw_rates.items():
            try:
                weekday_rates[int(key)] = float(val)
            except (TypeError, ValueError):
                continue
    if not weekday_rates:
        weekday_rates = {5: 0.25, 6: 1.0}
    return {
        "weekday_rates": weekday_rates,
        "min_hours": float(c.get("min_hours") or 1.0),
        "flat_hours": float(c.get("flat_hours") or 1.0),
        "requires_astreinte_same_iso_week": bool(
            c.get("requires_astreinte_same_iso_week", True)
        ),
        "weekend_weekday_numbers": list(c.get("weekend_weekday_numbers") or [5, 6]),
    }


def _week_monday(d: date) -> date:
    from datetime import timedelta

    return d - timedelta(days=d.weekday())


def evaluate_astreinte_weekend_majoration(
    rule: dict[str, Any],
    *,
    year: int,
    month: int,
    calendrier_reel: list[dict[str, Any]],
    astreinte_shift_dates: list[date],
    hourly_rate: float,
) -> list[dict[str, Any]]:
    """Retourne une ligne par jour week-end éligible."""
    conditions = rule.get("conditions") or {}
    cfg = _default_conditions(conditions)
    if hourly_rate <= 0:
        return []

    astreinte_mondays = astreinte_week_mondays(astreinte_shift_dates)
    weekend_days = weekend_work_days(
        calendrier_reel,
        year,
        month,
        cfg["weekend_weekday_numbers"],
    )

    weekday_labels = {5: "samedi", 6: "dimanche"}
    results: list[dict[str, Any]] = []

    for entry in weekend_days:
        heures = float(entry.get("heures_faites") or 0)
        if heures < cfg["min_hours"]:
            continue
        jour = int(entry["jour"])
        work_date = date(year, month, jour)
        weekday = work_date.weekday()
        rate = cfg["weekday_rates"].get(weekday)
        if rate is None or rate <= 0:
            continue

        if cfg["requires_astreinte_same_iso_week"]:
            if _week_monday(work_date) not in astreinte_mondays:
                continue

        amount = round(hourly_rate * cfg["flat_hours"] * rate, 2)
        if amount <= 0:
            continue

        label_day = weekday_labels.get(weekday, f"jour_{weekday}")
        results.append(
            {
                "amount": amount,
                "quantity": cfg["flat_hours"],
                "label": f"Majoration astreinte {label_day}",
                "work_date": work_date.isoformat(),
                "weekday": weekday,
                "majoration_rate": rate,
                "hourly_rate": hourly_rate,
                "rule_code": rule.get("code"),
                "details": {
                    "heures_faites": heures,
                    "min_hours": cfg["min_hours"],
                    "flat_hours": cfg["flat_hours"],
                    "majoration_rate": rate,
                    "work_date": work_date.isoformat(),
                },
            }
        )

    return results
