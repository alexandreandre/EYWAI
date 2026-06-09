"""Persistance company_jei_exonerations via Supabase (service role)."""

from __future__ import annotations

from app.core.database import supabase
from app.modules.jei_settings.domain.exonerations_interfaces import (
    AbstractJeiExonerationsRepository,
)


class SupabaseJeiExonerationsRepository(AbstractJeiExonerationsRepository):
    """Suivi cumulatif des exonérations JEI par établissement."""

    def sum_annual_excluding_month(
        self,
        company_id: str,
        year: int,
        exclude_employee_id: str,
        exclude_month: int,
    ) -> float:
        r = (
            supabase.table("company_jei_exonerations")
            .select("montant_exonere, employee_id, month")
            .eq("company_id", company_id)
            .eq("year", year)
            .execute()
        )
        total = 0.0
        for row in r.data or []:
            if (
                str(row.get("employee_id")) == str(exclude_employee_id)
                and int(row.get("month", 0)) == exclude_month
            ):
                continue
            total += float(row.get("montant_exonere") or 0.0)
        return round(total, 2)

    def upsert_monthly(
        self,
        company_id: str,
        year: int,
        month: int,
        employee_id: str,
        montant_exonere: float,
    ) -> None:
        supabase.table("company_jei_exonerations").upsert(
            {
                "company_id": company_id,
                "year": year,
                "month": month,
                "employee_id": employee_id,
                "montant_exonere": round(montant_exonere, 2),
            },
            on_conflict="company_id,year,month,employee_id",
        ).execute()


jei_exonerations_repository = SupabaseJeiExonerationsRepository()
