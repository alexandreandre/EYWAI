"""Éligibilité et quantité — indemnité km astreinte (domaine pur)."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from app.modules.payroll.engine.calcul_frais import indemnite_km_astreinte


def _default_conditions(conditions: dict[str, Any] | None) -> dict[str, Any]:
    c = dict(conditions or {})
    return {
        "km_free_threshold_one_way": float(c.get("km_free_threshold_one_way", 10)),
        "round_trip_multiplier": float(c.get("round_trip_multiplier", 2)),
        "requires_astreinte": bool(c.get("requires_astreinte", True)),
        "requires_weekend_work": bool(c.get("requires_weekend_work", True)),
        "weekend_weekday_numbers": list(c.get("weekend_weekday_numbers") or [5, 6]),
        "astreinte_link_mode": str(c.get("astreinte_link_mode") or "month_overlap"),
        "quantity_mode": str(c.get("quantity_mode") or "once_if_eligible"),
        "rate_mode": str(c.get("rate_mode") or "coefficient_a"),
        "vehicle_type_default": str(c.get("vehicle_type_default") or "voitures"),
        "bareme_segment_index": int(c.get("bareme_segment_index") or 0),
        "manual_trips_input_name": c.get("manual_trips_input_name"),
    }


def weekend_work_days(
    calendrier_reel: list[dict[str, Any]],
    year: int,
    month: int,
    weekend_weekdays: list[int] | None = None,
) -> list[dict[str, Any]]:
    """Jours du mois avec heures pointées un samedi ou dimanche."""
    wd_set = set(weekend_weekdays or [5, 6])
    out: list[dict[str, Any]] = []
    for entry in calendrier_reel or []:
        if not isinstance(entry, dict):
            continue
        jour = entry.get("jour")
        heures = float(entry.get("heures_faites") or 0)
        if not jour or heures <= 0:
            continue
        try:
            d = date(year, month, int(jour))
        except (TypeError, ValueError):
            continue
        if d.weekday() in wd_set:
            out.append({**entry, "date": d.isoformat(), "weekday": d.weekday()})
    return out


def astreinte_week_mondays(shift_dates: list[date]) -> set[date]:
    """Lundis ISO des semaines contenant une astreinte."""
    mondays: set[date] = set()
    for d in shift_dates:
        mondays.add(d - timedelta(days=d.weekday()))
    return mondays


def _week_monday_for_day(year: int, month: int, jour: int) -> date | None:
    try:
        d = date(year, month, int(jour))
    except (TypeError, ValueError):
        return None
    return d - timedelta(days=d.weekday())


def _weekend_week_mondays(
    weekend_days: list[dict[str, Any]],
    year: int,
    month: int,
) -> set[date]:
    mondays: set[date] = set()
    for entry in weekend_days:
        jour = entry.get("jour")
        if jour is None:
            continue
        monday = _week_monday_for_day(year, month, int(jour))
        if monday:
            mondays.add(monday)
    return mondays


def qualifying_week_mondays(
    astreinte_mondays: set[date],
    weekend_days: list[dict[str, Any]],
    year: int,
    month: int,
    link_mode: str,
) -> set[date]:
    if not astreinte_mondays or not weekend_days:
        return set()
    weekend_mondays = _weekend_week_mondays(weekend_days, year, month)
    if link_mode == "month_overlap":
        return astreinte_mondays & weekend_mondays
    return astreinte_mondays & weekend_mondays


def is_eligible_astreinte_km(
    conditions: dict[str, Any],
    *,
    astreinte_mondays: set[date],
    weekend_days: list[dict[str, Any]],
    year: int,
    month: int,
) -> bool:
    cfg = _default_conditions(conditions)
    if cfg["requires_astreinte"] and not astreinte_mondays:
        return False
    if cfg["requires_weekend_work"] and not weekend_days:
        return False
    if cfg["astreinte_link_mode"] == "same_iso_week":
        qualifying = qualifying_week_mondays(
            astreinte_mondays, weekend_days, year, month, "same_iso_week"
        )
        return len(qualifying) > 0
    return True


def resolve_astreinte_km_quantity(
    conditions: dict[str, Any],
    *,
    qualifying_weeks: set[date],
    weekend_days: list[dict[str, Any]],
    manual_trips: float = 0.0,
) -> float:
    cfg = _default_conditions(conditions)
    mode = cfg["quantity_mode"]
    if mode == "once_if_eligible":
        return 1.0
    if mode == "per_qualifying_week":
        return float(len(qualifying_weeks))
    if mode == "per_weekend_work_day":
        return float(len(weekend_days))
    if mode == "per_manual_trips":
        return max(0.0, float(manual_trips))
    return 0.0


def read_deplacement_astreinte(
    employee: dict[str, Any],
) -> dict[str, Any] | None:
    spec = employee.get("specificites_paie") or {}
    if not isinstance(spec, dict):
        return None
    block = spec.get("deplacement_astreinte")
    if not isinstance(block, dict):
        return None
    if block.get("enabled") is False:
        return None
    return block


def evaluate_astreinte_weekend_km(
    rule: dict[str, Any],
    employee: dict[str, Any],
    *,
    year: int,
    month: int,
    calendrier_reel: list[dict[str, Any]],
    astreinte_shift_dates: list[date],
    baremes_km: dict[str, Any] | None,
    manual_trips: float = 0.0,
) -> dict[str, Any]:
    """
    Évalue une règle per_astreinte_weekend_km.
    Retourne dict avec amount, quantity, eligible, details.
    """
    conditions = rule.get("conditions") or {}
    cfg = _default_conditions(conditions)
    details: dict[str, Any] = {
        "eligible": False,
        "quantity_mode": cfg["quantity_mode"],
        "astreinte_link_mode": cfg["astreinte_link_mode"],
    }

    deplacement = read_deplacement_astreinte(employee)
    if not deplacement:
        details["skip_reason"] = "employee_not_configured"
        return {"amount": 0.0, "quantity": 0.0, "eligible": False, "details": details}

    distance = deplacement.get("distance_km_one_way")
    vehicle_cv = deplacement.get("vehicle_cv")
    if distance is None or vehicle_cv is None:
        details["skip_reason"] = "missing_distance_or_cv"
        return {"amount": 0.0, "quantity": 0.0, "eligible": False, "details": details}

    vehicle_type = str(
        deplacement.get("vehicle_type") or cfg["vehicle_type_default"]
    )
    astreinte_mondays = astreinte_week_mondays(astreinte_shift_dates)
    weekend_days = weekend_work_days(
        calendrier_reel,
        year,
        month,
        cfg["weekend_weekday_numbers"],
    )
    qualifying_weeks = qualifying_week_mondays(
        astreinte_mondays,
        weekend_days,
        year,
        month,
        cfg["astreinte_link_mode"],
    )

    if not is_eligible_astreinte_km(
        conditions,
        astreinte_mondays=astreinte_mondays,
        weekend_days=weekend_days,
        year=year,
        month=month,
    ):
        if cfg["requires_astreinte"] and not astreinte_mondays:
            details["skip_reason"] = "no_astreinte"
        elif cfg["requires_weekend_work"] and not weekend_days:
            details["skip_reason"] = "no_weekend_work"
        else:
            details["skip_reason"] = "astreinte_weekend_not_linked"
        return {"amount": 0.0, "quantity": 0.0, "eligible": False, "details": details}

    quantity = resolve_astreinte_km_quantity(
        conditions,
        qualifying_weeks=qualifying_weeks,
        weekend_days=weekend_days,
        manual_trips=manual_trips,
    )
    if quantity <= 0:
        details["skip_reason"] = "zero_quantity"
        return {"amount": 0.0, "quantity": 0.0, "eligible": False, "details": details}

    unit_amount, km_details = indemnite_km_astreinte(
        baremes_km,
        float(distance),
        float(vehicle_cv),
        vehicle_type,
        threshold_one_way=cfg["km_free_threshold_one_way"],
        round_trip_multiplier=cfg["round_trip_multiplier"],
        rate_mode=cfg["rate_mode"],
        bareme_segment_index=cfg["bareme_segment_index"],
    )
    details.update(km_details)
    details["quantity"] = quantity
    details["vehicle_cv"] = float(vehicle_cv)
    details["vehicle_type"] = vehicle_type

    if unit_amount is None:
        return {"amount": 0.0, "quantity": 0.0, "eligible": False, "details": details}

    amount = round(unit_amount * quantity, 2)
    details["unit_amount"] = unit_amount
    details["eligible"] = True
    return {
        "amount": amount,
        "quantity": quantity,
        "eligible": True,
        "details": details,
    }
