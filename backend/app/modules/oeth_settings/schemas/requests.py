"""Schémas requêtes API OETH."""

from __future__ import annotations

from datetime import date
from typing import List, Optional

from pydantic import BaseModel, Field


class OethSettingsUpdate(BaseModel):
    oeth_assujetti_override: Optional[bool] = None
    date_franchissement_seuil_20: Optional[date] = None
    accord_agree_code: Optional[str] = None
    accord_agree_valid_from: Optional[date] = None
    accord_agree_valid_to: Optional[date] = None
    declaring_establishment_siret: Optional[str] = None
    departement: Optional[str] = None
    taux_obligation: Optional[float] = Field(default=None, ge=0, le=1)


class EmployeeBoethUpdate(BaseModel):
    boeth_code: str = Field(..., min_length=2, max_length=2)
    valid_from: date
    valid_to: Optional[date] = None
    document_type: Optional[str] = None
    document_expires_at: Optional[date] = None
    notes: Optional[str] = None


class BoethExterneItem(BaseModel):
    external_type: str
    annual_average_count: float = Field(ge=0)
    contract_reference: Optional[str] = None
    amount_ht: float = Field(default=0, ge=0)


class BoethExternesUpdate(BaseModel):
    items: List[BoethExterneItem] = Field(default_factory=list)


class DeductionItem(BaseModel):
    deduction_type: str
    amount_eur: float = Field(ge=0)
    provider_name: Optional[str] = None
    reference: Optional[str] = None


class DeductionsUpdate(BaseModel):
    items: List[DeductionItem] = Field(default_factory=list)


class EcapPositionItem(BaseModel):
    job_code_pcs_ese: str
    annual_average_count: float = Field(ge=0)


class EcapPositionsUpdate(BaseModel):
    items: List[EcapPositionItem] = Field(default_factory=list)


class UrssafOverrideUpdate(BaseModel):
    urssaf_ema_assujettissement: Optional[float] = None
    urssaf_ema_boeth: Optional[float] = None
    urssaf_ema_ecap: Optional[float] = None
    urssaf_notified_at: Optional[date] = None


class AnnualReviewStatusUpdate(BaseModel):
    status: str = Field(..., pattern="^(draft|validated|declared)$")
