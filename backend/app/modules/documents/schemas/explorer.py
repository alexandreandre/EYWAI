"""Réponses API — explorateur documents entreprise."""

from __future__ import annotations

from typing import List, Literal

from pydantic import BaseModel

from app.modules.documents.schemas.responses import GeneratedDocument


class ExplorerPayslipItem(BaseModel):
    id: str
    employee_id: str
    employee_name: str
    name: str
    url: str
    month: int
    year: int


class ExplorerStorageItem(BaseModel):
    employee_id: str
    employee_name: str
    kind: Literal["contract", "identity", "credentials"]
    url: str
    label: str


class DocumentsExplorerResponse(BaseModel):
    generated: List[GeneratedDocument]
    payslips: List[ExplorerPayslipItem]
    storage: List[ExplorerStorageItem]
