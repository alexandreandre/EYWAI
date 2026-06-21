"""Schémas entrée API suivi IJSS."""

from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, Field


class IjssImportParseBody(BaseModel):
    column_mapping: Optional[Dict[str, str]] = None


class IjssMatchReceivedBody(BaseModel):
    employee_id: str
    expected_line_id: Optional[str] = None


class IjssJustifyBody(BaseModel):
    content: str = Field(..., min_length=3)
    received_line_id: Optional[str] = None


class IjssValidateBody(BaseModel):
    amount: Optional[float] = Field(default=None, ge=0)
    source: Optional[Literal["cpam_decompte", "bank_transfer", "manual"]] = None


class IjssClosePeriodBody(BaseModel):
    notes: Optional[str] = None


class IjssImportProfileUpdateBody(BaseModel):
    column_mapping: Dict[str, Any] = Field(default_factory=dict)
