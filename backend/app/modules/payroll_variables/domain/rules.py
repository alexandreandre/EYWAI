"""Règles calcul variables paie — domaine pur."""

from __future__ import annotations

from typing import Any, Literal

RuleType = Literal[
    "fixed_monthly",
    "per_astreinte_week",
    "per_shift_type",
    "per_modulation_payout",
    "per_night_hour",
]


def compute_rule_amount(
    rule_type: str,
    amount: float | None,
    rate: float | None,
    quantity: float,
    *,
    conditions: dict[str, Any] | None = None,
) -> float:
    conditions = conditions or {}
    if rule_type == "fixed_monthly":
        return round(float(amount or 0), 2)
    if rule_type == "per_astreinte_week":
        return round(float(amount or 0) * quantity, 2)
    if rule_type == "per_shift_type":
        return round(float(amount or 0) * quantity, 2)
    if rule_type == "per_night_hour":
        unit = float(rate if rate is not None else amount or 0)
        return round(unit * quantity, 2)
    if rule_type == "per_modulation_payout":
        min_balance = float(conditions.get("min_balance_hours") or 0)
        if quantity < min_balance:
            return 0.0
        return round(float(amount or 0) * quantity, 2)
    return 0.0


def employee_matches_conditions(
    employee: dict[str, Any],
    conditions: dict[str, Any] | None,
) -> bool:
    if not conditions:
        return True
    statuts = conditions.get("statuts")
    if statuts and isinstance(statuts, list):
        emp_statut = (employee.get("statut") or "").lower()
        if not any(s.lower() in emp_statut for s in statuts):
            return False
    exclude_statuts = conditions.get("exclude_statuts")
    if exclude_statuts and isinstance(exclude_statuts, list):
        emp_statut = (employee.get("statut") or "").lower()
        if any(s.lower() in emp_statut for s in exclude_statuts):
            return False
    min_productivity = conditions.get("min_productivity_amount")
    if min_productivity is not None:
        pass
    return True
