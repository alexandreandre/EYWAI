"""Schémas entrée API import DSN."""

from __future__ import annotations

from typing import Any, Dict

from pydantic import BaseModel, EmailStr, Field


class DsnImportCommitBody(BaseModel):
    overrides: Dict[str, str] = Field(default_factory=dict)
    payload_edits: Dict[str, Dict[str, Any]] = Field(default_factory=dict)


class DsnImportRevalidateBody(BaseModel):
    payload_edits: Dict[str, Dict[str, Any]] = Field(default_factory=dict)


class ActivateImportedEmployeeBody(BaseModel):
    employee_id: str
    company_id: str
    email: EmailStr
