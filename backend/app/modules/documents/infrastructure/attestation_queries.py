"""Lectures d'une attestation : bulletins remis et période d'essai en cours (05/11/2026)."""

from __future__ import annotations

from datetime import date
from typing import Any, Optional

from app.core.database import supabase
from app.modules.documents.domain.fin_de_contrat import lire_date
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


def dernier_jour_de_depart(employee_id: str, company_id: str) -> Optional[date]:
    """Le dernier jour travaillé du départ le plus récent (un départ annulé ne compte pas).

    Lu sur les départs du salarié : `current_exit_id` est vide une fois le salarié parti.
    """
    r = (
        supabase.table("employee_exits")
        .select("last_working_day, status")
        .eq("employee_id", employee_id)
        .eq("company_id", company_id)
        .execute()
    )
    jours = [
        jour
        for ligne in ((r.data or []) if r else [])
        if ligne.get("status") != "annulee" and (jour := lire_date(ligne.get("last_working_day")))
    ]
    return max(jours) if jours else None
