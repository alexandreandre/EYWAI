"""Schémas entrée API suivi IJSS."""

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class IjssImportParseBody(BaseModel):
    column_mapping: Optional[Dict[str, str]] = None


class IjssMatchReceivedBody(BaseModel):
    employee_id: str
    expected_line_id: Optional[str] = None


class IjssJustifyBody(BaseModel):
    content: str = Field(..., min_length=3)
    received_line_id: Optional[str] = None


class IjssClosePeriodBody(BaseModel):
    notes: Optional[str] = None
