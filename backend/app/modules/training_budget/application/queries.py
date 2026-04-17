"""Lecture budget formation avec consommation (repo training)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Literal, Optional, Tuple

from app.modules.training.infrastructure.repository import training_repository
from app.modules.training_budget.infrastructure.repository import training_budget_repository
from app.modules.training_budget.schemas.responses import (
    TrainingBudget,
    TrainingBudgetWithConsumption,
)


def _parse_dt(val: Any) -> Optional[datetime]:
    if val is None:
        return None
    if isinstance(val, datetime):
        return val
    if isinstance(val, date):
        return datetime.combine(val, datetime.min.time())
    return datetime.fromisoformat(str(val).replace("Z", "+00:00"))


def _budget_model(row: Dict[str, Any]) -> TrainingBudget:
    r = dict(row)
    sb = r.get("service_breakdown")
    if not isinstance(sb, dict):
        sb = {}
    return TrainingBudget(
        id=str(r["id"]),
        company_id=str(r["company_id"]),
        year=int(r["year"]),
        global_envelope=float(r.get("global_envelope") or 0),
        alert_threshold_1=float(r.get("alert_threshold_1") or 70),
        alert_threshold_2=float(r.get("alert_threshold_2") or 90),
        service_breakdown=dict(sb),
        created_at=_parse_dt(r.get("created_at")),
        updated_at=_parse_dt(r.get("updated_at")),
    )


def _consumption_metrics(
    budget: TrainingBudget, consumed: float
) -> Tuple[float, float, float, Literal["none", "warning", "critical"]]:
    envelope = budget.global_envelope
    t1 = budget.alert_threshold_1
    t2 = budget.alert_threshold_2
    remaining = envelope - consumed
    if envelope > 0:
        consumption_pct = (consumed / envelope) * 100.0
    else:
        consumption_pct = 0.0

    if consumption_pct >= t2:
        alert_level: Literal["none", "warning", "critical"] = "critical"
    elif consumption_pct >= t1:
        alert_level = "warning"
    else:
        alert_level = "none"

    return consumed, remaining, consumption_pct, alert_level


def _with_consumption(row: Dict[str, Any], consumed: float) -> TrainingBudgetWithConsumption:
    base = _budget_model(row)
    c, rem, pct, alert_level = _consumption_metrics(base, consumed)
    return TrainingBudgetWithConsumption(
        **base.model_dump(),
        consumed=c,
        remaining=rem,
        consumption_pct=pct,
        alert_level=alert_level,
    )


def get_budget(company_id: str, year: int) -> TrainingBudgetWithConsumption:
    row = training_budget_repository.get_by_year(company_id, year)
    if not row:
        raise LookupError(f"Aucun budget défini pour l'année {year}.")
    consumed = training_repository.get_total_consumed(company_id, year)
    return _with_consumption(row, consumed)


def get_all_budgets(company_id: str) -> List[TrainingBudgetWithConsumption]:
    rows = training_budget_repository.get_all(company_id)
    out: List[TrainingBudgetWithConsumption] = []
    for row in rows:
        y = int(row["year"])
        consumed = training_repository.get_total_consumed(company_id, y)
        out.append(_with_consumption(row, consumed))
    return out
