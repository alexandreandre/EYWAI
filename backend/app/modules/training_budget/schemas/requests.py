"""Schémas de requête budget formation."""

from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, model_validator


class TrainingBudgetCreate(BaseModel):
    year: int
    global_envelope: float = Field(gt=0)
    alert_threshold_1: float = Field(default=70.0, ge=1, le=99)
    alert_threshold_2: float = Field(default=90.0, ge=2, le=100)
    service_breakdown: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_thresholds_order(self) -> "TrainingBudgetCreate":
        if self.alert_threshold_2 <= self.alert_threshold_1:
            raise ValueError(
                "alert_threshold_2 doit être strictement supérieur à alert_threshold_1."
            )
        if self.alert_threshold_2 > 100:
            raise ValueError("alert_threshold_2 ne peut pas dépasser 100.")
        return self


class TrainingBudgetUpdate(BaseModel):
    global_envelope: Optional[float] = None
    alert_threshold_1: Optional[float] = None
    alert_threshold_2: Optional[float] = None
    service_breakdown: Optional[Dict[str, Any]] = None

    @model_validator(mode="after")
    def validate_thresholds(self) -> "TrainingBudgetUpdate":
        t1 = self.alert_threshold_1
        t2 = self.alert_threshold_2
        if t1 is not None and (t1 < 1 or t1 > 99):
            raise ValueError("alert_threshold_1 doit être entre 1 et 99.")
        if t2 is not None and (t2 < 2 or t2 > 100):
            raise ValueError("alert_threshold_2 doit être entre 2 et 100.")
        if t1 is not None and t2 is not None:
            if t2 <= t1:
                raise ValueError(
                    "alert_threshold_2 doit être strictement supérieur à alert_threshold_1."
                )
            if t2 < t1 + 1:
                raise ValueError(
                    "alert_threshold_2 doit être au moins alert_threshold_1 + 1."
                )
        return self


class TrainingBudgetPutBody(BaseModel):
    """Corps PUT /{year} : crée ou met à jour l'enveloppe pour l'année (path)."""

    global_envelope: float = Field(gt=0)
    alert_threshold_1: float = Field(default=70.0, ge=1, le=99)
    alert_threshold_2: float = Field(default=90.0, ge=2, le=100)
    service_breakdown: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_thresholds_order(self) -> "TrainingBudgetPutBody":
        if self.alert_threshold_2 <= self.alert_threshold_1:
            raise ValueError(
                "alert_threshold_2 doit être strictement supérieur à alert_threshold_1."
            )
        if self.alert_threshold_2 > 100:
            raise ValueError("alert_threshold_2 ne peut pas dépasser 100.")
        return self


__all__ = ["TrainingBudgetCreate", "TrainingBudgetUpdate", "TrainingBudgetPutBody"]
