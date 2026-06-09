"""Schémas réponses API OETH."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class OethSettings(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Optional[str] = None
    company_id: str
    oeth_assujetti_override: Optional[bool] = None
    oeth_assujetti: bool = False
    date_franchissement_seuil_20: Optional[date] = None
    neutralisation_active: bool = False
    accord_agree_code: Optional[str] = None
    accord_agree_valid_from: Optional[date] = None
    accord_agree_valid_to: Optional[date] = None
    declaring_establishment_siret: Optional[str] = None
    departement: Optional[str] = None
    taux_obligation: float = 0.06
    effectif_actif: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class EmployeeBoethProfile(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Optional[str] = None
    employee_id: str
    company_id: str
    boeth_code: str
    boeth_label: Optional[str] = None
    valid_from: date
    valid_to: Optional[date] = None
    document_type: Optional[str] = None
    document_expires_at: Optional[date] = None
    notes: Optional[str] = None
    is_active: bool = True


class BoethStatusHistoryItem(BaseModel):
    id: Optional[str] = None
    previous_boeth_code: Optional[str] = None
    new_boeth_code: Optional[str] = None
    changed_at: date
    changed_in_period: Optional[str] = None


class OethCompliance(BaseModel):
    effectif_actif: int
    boeth_count: int
    taux_emploi_pct: float
    quota_6_pct: int
    boeth_manquants: int
    oeth_assujetti: bool
    neutralisation_active: bool
    accord_agree_active: bool
    alertes: List[str] = Field(default_factory=list)


class BoethExterne(BaseModel):
    id: Optional[str] = None
    external_type: str
    external_label: Optional[str] = None
    annual_average_count: float
    contract_reference: Optional[str] = None
    amount_ht: float = 0


class OethDeduction(BaseModel):
    id: Optional[str] = None
    deduction_type: str
    deduction_label: Optional[str] = None
    amount_eur: float
    provider_name: Optional[str] = None
    reference: Optional[str] = None


class OethEcapPosition(BaseModel):
    id: Optional[str] = None
    job_code_pcs_ese: str
    annual_average_count: float


class OethAnnualReview(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Optional[str] = None
    company_id: str
    employment_year: int
    ema_assujettissement: Optional[float] = None
    ema_boeth_interne: Optional[float] = None
    ema_boeth_externe: Optional[float] = None
    ema_ecap: Optional[float] = None
    urssaf_ema_assujettissement: Optional[float] = None
    urssaf_ema_boeth: Optional[float] = None
    urssaf_ema_ecap: Optional[float] = None
    urssaf_notified_at: Optional[date] = None
    boeth_manquants: Optional[int] = None
    contribution_brute: Optional[float] = None
    contribution_nette: Optional[float] = None
    contribution_due: Optional[float] = None
    deductions_detail: Dict[str, Any] = Field(default_factory=dict)
    neutralisation_active: bool = False
    surcontribution_applicable: bool = False
    accord_agree_active: bool = False
    status: str = "draft"
    declared_in_dsn_period: Optional[str] = None
    taux_emploi_pct: Optional[float] = None
    quota_boeth: Optional[int] = None
    externes: List[BoethExterne] = Field(default_factory=list)
    deductions: List[OethDeduction] = Field(default_factory=list)
    ecap_positions: List[OethEcapPosition] = Field(default_factory=list)


class OethDsnPayload(BaseModel):
    employment_year: int
    period_rattachement_debut: str
    period_rattachement_fin: str
    complement_oeth: List[Dict[str, Any]] = Field(default_factory=list)
    cotisations_etablissement: List[Dict[str, Any]] = Field(default_factory=list)
    cotisation_agregee: Optional[Dict[str, Any]] = None
