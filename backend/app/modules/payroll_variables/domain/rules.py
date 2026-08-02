"""Règles calcul variables paie — domaine pur."""

from __future__ import annotations

from typing import Any, Literal

RuleType = Literal[
    "fixed_monthly",
    "per_astreinte_week",
    "per_shift_type",
    "per_modulation_payout",
    "per_night_hour",
    "per_astreinte_weekend_km",
    "per_astreinte_week_tiered",
    "per_astreinte_weekend_majoration",
    "per_week_without_absence",
    "transport_domicile_travail",
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
    if rule_type == "per_week_without_absence":
        per_week = float(conditions.get("amount_per_week") or amount or 0)
        return round(per_week * quantity, 2)
    return 0.0


def employee_matches_conditions(
    employee: dict[str, Any],
    conditions: dict[str, Any] | None,
) -> bool:
    if not conditions:
        return True
    employee_ids = conditions.get("employee_ids")
    if isinstance(employee_ids, list):
        # Liste vide = règle ciblée mais sans destinataire : ne cible personne.
        cibles = {str(x) for x in employee_ids}
        if str(employee.get("id") or "") not in cibles:
            return False
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
