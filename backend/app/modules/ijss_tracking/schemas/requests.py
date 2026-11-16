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


class IjRecuesBody(BaseModel):
    """IJ du mois connues (écran « Arrêts et IJ ») : un geste, montant brut."""

    year: int = Field(..., ge=2020, le=2100)
    month: int = Field(..., ge=1, le=12)
    montant: float = Field(..., ge=0, le=100_000)


class JustificatifArretBody(BaseModel):
    kind: Literal["virement_cpam", "ij_salarie", "decompte_cpam", "autre"]
    storage_path: str = Field(..., min_length=3, max_length=500)
    filename: Optional[str] = Field(default=None, max_length=255)
