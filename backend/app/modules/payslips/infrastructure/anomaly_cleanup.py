"""
Purge des alertes moteur paie figées dans payslip_data (réduction du bruit persisté).
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

from app.core.database import supabase
from app.modules.payslips.domain.anomaly_visibility import (
    is_period_after_last_working_day,
    parse_date_value,
)
from app.modules.payslips.infrastructure.repository import payslip_repository


def strip_engine_alerts_from_payslip_data(
    payslip_data: Dict[str, Any],
) -> Dict[str, Any]:
    """Retire alertes_baremes et alertes_maintien (copie immuable)."""
    cleaned = dict(payslip_data)
    cleaned.pop("alertes_baremes", None)

    synthese = cleaned.get("synthese_net")
    if isinstance(synthese, dict):
        synthese_clean = dict(synthese)
        synthese_clean.pop("alertes_maintien", None)
        cleaned["synthese_net"] = synthese_clean

    return cleaned


def purge_engine_alerts_on_payslip(
    payslip_id: str,
    supabase_client: Any = None,
) -> None:
    """Nettoie payslip_data.alertes_* pour un bulletin donné."""
    sb = supabase_client or supabase
    row = (
        sb.table("payslips")
        .select("payslip_data")
        .eq("id", payslip_id)
        .maybe_single()
        .execute()
    )
    if not row or not row.data:
        return
    pdata = row.data.get("payslip_data")
    if not isinstance(pdata, dict):
        return
    cleaned = strip_engine_alerts_from_payslip_data(pdata)
    if cleaned == pdata:
        return
    sb.table("payslips").update({"payslip_data": cleaned}).eq("id", payslip_id).execute()


def _fetch_employee_payslips(
    employee_id: str,
    company_id: str,
    supabase_client: Any,
) -> List[Dict[str, Any]]:
    r = (
        supabase_client.table("payslips")
        .select("id, year, month, status, payslip_data, bulletin_kind")
        .eq("employee_id", employee_id)
        .eq("company_id", company_id)
        .execute()
    )
    return [dict(row) for row in (r.data or []) if isinstance(row, dict)]


def cleanup_payslips_on_exit_archived(
    employee_id: str,
    company_id: str,
    last_working_day: Optional[date],
    supabase_client: Any = None,
) -> None:
    """
    À l'archivage d'une sortie :
    - supprime les brouillons postérieurs au dernier mois travaillé ;
    - retire les alertes moteur des bulletins validés restants.
    """
    sb = supabase_client or supabase
    lwd = last_working_day
    rows = _fetch_employee_payslips(employee_id, company_id, sb)

    for row in rows:
        payslip_id = str(row.get("id") or "")
        if not payslip_id:
            continue
        year = int(row.get("year") or 0)
        month = int(row.get("month") or 0)
        status = str(row.get("status") or "brouillon")

        # Les bulletins de régularisation (ex. participation versée l'année suivant
        # le départ) sont par nature postérieurs au dernier jour travaillé : ils ne
        # doivent jamais être supprimés à l'archivage de la sortie.
        if row.get("bulletin_kind"):
            continue

        if lwd and is_period_after_last_working_day(lwd, year, month):
            if status != "valide":
                payslip_repository.delete(payslip_id)
            continue

        if status == "valide":
            pdata = row.get("payslip_data")
            if isinstance(pdata, dict):
                cleaned = strip_engine_alerts_from_payslip_data(pdata)
                if cleaned != pdata:
                    sb.table("payslips").update({"payslip_data": cleaned}).eq(
                        "id", payslip_id
                    ).execute()


def parse_exit_last_working_day(exit_data: Dict[str, Any]) -> Optional[date]:
    return parse_date_value(exit_data.get("last_working_day"))


def purge_all_engine_alerts_from_payslips(
    supabase_client: Any = None,
    *,
    page_size: int = 100,
) -> int:
    """
    Retire alertes_baremes / alertes_maintien de tous les bulletins existants.
    Retourne le nombre de bulletins mis à jour.
    """
    sb = supabase_client or supabase
    updated = 0
    offset = 0

    while True:
        r = (
            sb.table("payslips")
            .select("id, payslip_data")
            .range(offset, offset + page_size - 1)
            .execute()
        )
        rows = [dict(row) for row in (r.data or []) if isinstance(row, dict)]
        if not rows:
            break

        for row in rows:
            payslip_id = str(row.get("id") or "")
            pdata = row.get("payslip_data")
            if not payslip_id or not isinstance(pdata, dict):
                continue
            cleaned = strip_engine_alerts_from_payslip_data(pdata)
            if cleaned == pdata:
                continue
            sb.table("payslips").update({"payslip_data": cleaned}).eq(
                "id", payslip_id
            ).execute()
            updated += 1

        if len(rows) < page_size:
            break
        offset += page_size

    return updated
