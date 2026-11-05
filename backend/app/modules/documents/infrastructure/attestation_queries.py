"""Lectures d'une attestation : bulletins remis et période d'essai en cours (05/11/2026)."""

from __future__ import annotations

from typing import Any, Optional

from app.core.database import supabase
from app.modules.payslips.domain.mise_a_disposition import bulletins_remis
from app.modules.payslips.infrastructure.mise_a_disposition_queries import jour_de_la_societe
from app.shared.domain.temps_local import aujourd_hui_local


def bulletins_remis_du_salarie(employee_id: str, company_id: str) -> list[dict[str, Any]]:
    """Les bulletins que le salarié voit ce jour-là : validés, et arrivés à la date de
    mise à disposition réglée par la société (même règle que son espace)."""
    r = (
        supabase.table("payslips")
        .select("year, month, status, validated_at, payslip_data")
        .eq("employee_id", employee_id)
        .eq("company_id", company_id)
        .eq("status", "valide")
        .execute()
    )
    lignes = (r.data or []) if r else []
    if not lignes:
        return []
    return [
        dict(bulletin)
        for bulletin in bulletins_remis(
            lignes, jour=jour_de_la_societe(company_id), aujourd_hui=aujourd_hui_local()
        )
    ]


def fin_de_periode_d_essai_en_cours(employee_id: str, company_id: str) -> Optional[str]:
    """Date de fin de la période d'essai en cours, ou None s'il n'y en a pas."""
    r = (
        supabase.table("trial_periods")
        .select("end_date")
        .eq("employee_id", employee_id)
        .eq("company_id", company_id)
        .eq("status", "en_cours")
        .limit(1)
        .execute()
    )
    lignes = (r.data or []) if r else []
    return (lignes[0].get("end_date") or None) if lignes else None
