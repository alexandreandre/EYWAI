"""Commandes budget formation."""

from __future__ import annotations

from typing import Any, Dict

from app.modules.training_budget.application import queries
from app.modules.training_budget.infrastructure.repository import training_budget_repository
from app.modules.training_budget.schemas.requests import TrainingBudgetPutBody
from app.modules.training_budget.schemas.responses import TrainingBudgetWithConsumption


def save_budget(
    company_id: str, year: int, data: TrainingBudgetPutBody
) -> TrainingBudgetWithConsumption:
    payload: Dict[str, Any] = {
        "year": year,
        "global_envelope": data.global_envelope,
        "alert_threshold_1": data.alert_threshold_1,
        "alert_threshold_2": data.alert_threshold_2,
        "service_breakdown": dict(data.service_breakdown or {}),
    }
    training_budget_repository.upsert(company_id, payload)
    return queries.get_budget(company_id, year)
