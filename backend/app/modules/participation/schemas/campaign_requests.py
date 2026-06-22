"""Schémas campagnes bulletin d'option."""

from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field

ChoiceType = Literal["full_cash", "partial_cash", "full_pee"]


class CampaignAdvanceInput(BaseModel):
    employee_id: str
    amount: float = Field(ge=0)
    label: str = ""


class CampaignAmountInput(BaseModel):
    employee_id: str
    participation_amount: float = Field(ge=0, default=0)
    interessement_amount: float = Field(ge=0, default=0)


class ParticipationCampaignCreate(BaseModel):
    simulation_id: Optional[str] = None
    year: int = Field(..., ge=2020, le=2100)
    exercise_label: str = ""
    payroll_year: Optional[int] = Field(None, ge=2020, le=2100)
    payroll_month: Optional[int] = Field(None, ge=1, le=12)
    advances: List[CampaignAdvanceInput] = Field(default_factory=list)
    amounts: List[CampaignAmountInput] = Field(default_factory=list)


class BulletinRespondRequest(BaseModel):
    choice_type: ChoiceType
    choice_cash_amount: Optional[float] = Field(None, ge=0)


class GeneratePayrollLinesRequest(BaseModel):
    payroll_year: int = Field(..., ge=2020, le=2100)
    payroll_month: int = Field(..., ge=1, le=12)
