"""Réponses API campagnes bulletin d'option."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class CampaignStats(BaseModel):
    total: int = 0
    pending: int = 0
    sent: int = 0
    responded: int = 0
    default_pee: int = 0
    cancelled: int = 0


class ParticipationCampaignListItem(BaseModel):
    id: str
    year: int
    exercise_label: str
    status: str
    sent_at: Optional[datetime] = None
    deadline_at: Optional[datetime] = None
    created_at: datetime
    stats: CampaignStats


class ParticipationCampaignDetail(BaseModel):
    id: str
    company_id: str
    simulation_id: Optional[str] = None
    year: int
    exercise_label: str
    status: str
    payroll_year: Optional[int] = None
    payroll_month: Optional[int] = None
    sent_at: Optional[datetime] = None
    deadline_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    stats: CampaignStats


class ParticipationBulletinItem(BaseModel):
    id: str
    campaign_id: str
    employee_id: str
    employee_first_name: Optional[str] = None
    employee_last_name: Optional[str] = None
    dispositif_type: str
    gross_amount: float
    csg_non_deductible: float
    csg_deductible: float
    advance_amount: float
    advance_label: str
    net_amount: float
    generated_document_id: Optional[str] = None
    status: str
    choice_type: Optional[str] = None
    choice_cash_amount: Optional[float] = None
    pee_amount: Optional[float] = None
    cash_amount: Optional[float] = None
    responded_at: Optional[datetime] = None
    deadline_at: Optional[datetime] = None
    exercise_label: Optional[str] = None
    year: Optional[int] = None


class ParticipationBulletinListResponse(BaseModel):
    bulletins: List[ParticipationBulletinItem]


class ParticipationCampaignListResponse(BaseModel):
    campaigns: List[ParticipationCampaignListItem]


class ParticipationCampaignCreateResponse(BaseModel):
    campaign: ParticipationCampaignDetail
    bulletins_created: int


class ParticipationCampaignActionResponse(BaseModel):
    campaign: ParticipationCampaignDetail
    detail: Optional[str] = None
    payroll_lines_created: Optional[int] = None


class EmployeeParticipationBulletinListResponse(BaseModel):
    bulletins: List[ParticipationBulletinItem]


class ImportResultResponse(BaseModel):
    campaign_id: Optional[str] = None
    bulletins: int = 0
    full_cash: int = 0
    partial_cash: int = 0
    full_pee: int = 0
    linked_inputs: int = 0
    skipped: bool = False
    dry_run: bool = False
    detail: str = ""
