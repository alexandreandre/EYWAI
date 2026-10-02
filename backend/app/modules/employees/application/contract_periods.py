"""Contrats passés d'un salarié. N'écrit pas l'ancienneté."""

from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel, Field, model_validator

from app.core.database import supabase


class ContractPeriodMissing(LookupError):
    """Aucune ligne pour cet identifiant dans la société du salarié."""


class ContractPeriodIn(BaseModel):
    contract_type: str = Field(min_length=1, max_length=40)
    date_debut: date
    date_fin: date

    @model_validator(mode="after")
    def fin_apres_debut(self) -> "ContractPeriodIn":
        if self.date_fin < self.date_debut:
            raise ValueError("La date de fin est avant la date de début.")
        self.contract_type = self.contract_type.strip()
        if not self.contract_type:
            raise ValueError("Le type de contrat est requis.")
        return self


def list_contract_periods(employee_id: str, company_id: str) -> list[dict[str, Any]]:
    res = (
        supabase.table("employee_contract_periods")
        .select("id, employee_id, company_id, contract_type, date_debut, date_fin, created_at")
        .eq("employee_id", employee_id)
        .eq("company_id", company_id)
        .order("date_debut", desc=True)
        .execute()
    )
    return list(res.data or [])


def add_contract_period(
    employee_id: str, company_id: str, payload: ContractPeriodIn
) -> dict[str, Any]:
    res = (
        supabase.table("employee_contract_periods")
        .insert(
            {
                "employee_id": employee_id,
                "company_id": company_id,
                "contract_type": payload.contract_type,
                "date_debut": payload.date_debut.isoformat(),
                "date_fin": payload.date_fin.isoformat(),
            }
        )
        .execute()
    )
    rows = list(res.data or [])
    if not rows:
        raise RuntimeError("Le contrat n'a pas été enregistré.")
    return rows[0]


def delete_contract_period(employee_id: str, company_id: str, period_id: str) -> None:
    existing = (
        supabase.table("employee_contract_periods")
        .select("id")
        .eq("id", period_id)
        .eq("employee_id", employee_id)
        .eq("company_id", company_id)
        .limit(1)
        .execute()
    )
    if not list(existing.data or []):
        raise ContractPeriodMissing("Contrat introuvable.")
    (
        supabase.table("employee_contract_periods")
        .delete()
        .eq("id", period_id)
        .eq("employee_id", employee_id)
        .eq("company_id", company_id)
        .execute()
    )
