"""
Queries infrastructure payslips : lecture BDD + URLs signées.

Logique alignée sur le router legacy (get_my_payslips, get_employee_payslips,
get_payslip_details, get_payslip_history). Utilise app.core.database.supabase.
"""

from __future__ import annotations

from typing import Any

from app.core.database import supabase

from app.modules.payslips.infrastructure.mappers import build_payslip_detail
from app.modules.payslips.infrastructure.storage_urls import (
    create_payslip_signed_urls,
    create_payslip_url_maps,
)


def get_employee_statut(employee_id: str) -> str | None:
    """Récupère le statut de l'employé (pour décision forfait jour vs heures)."""
    r = (
        supabase.table("employees")
        .select("statut")
        .eq("id", employee_id)
        .single()
        .execute()
    )
    return (r.data or {}).get("statut") if r else None


def get_payslip_meta(payslip_id: str) -> dict[str, Any] | None:
    """Récupère les champs minimaux d'un bulletin (company_id, employee_id) pour les contrôles d'accès."""
    r = (
        supabase.table("payslips")
        .select("company_id, employee_id")
        .eq("id", payslip_id)
        .single()
        .execute()
    )
    return r.data if r else None


def get_my_payslips(employee_id: str) -> list[dict[str, Any]]:
    """Liste des bulletins de l'employé avec net_a_payer et URLs signées."""
    r = (
        supabase.table("payslips")
        .select("id, month, year, pdf_storage_path, payslip_data")
        .eq("employee_id", employee_id)
        .order("year", desc=True)
        .order("month", desc=True)
        .execute()
    )
    payslips_db = (r.data or []) if r else []
    if not payslips_db:
        return []

    paths = [p["pdf_storage_path"] for p in payslips_db if p.get("pdf_storage_path")]
    if not paths:
        return []

    signed = create_payslip_url_maps(paths, 3600)
    download_map, preview_map = signed

    result = []
    for p in payslips_db:
        storage_path = p.get("pdf_storage_path")
        if storage_path not in download_map:
            continue
        file_name = storage_path.split("/")[-1]
        net_amount = None
        payslip_json = p.get("payslip_data")
        if isinstance(payslip_json, dict):
            val = payslip_json.get("net_a_payer")
            if isinstance(val, (int, float)):
                net_amount = float(val)
        result.append(
            {
                "id": p["id"],
                "name": file_name,
                "month": p["month"],
                "year": p["year"],
                "url": download_map[storage_path],
                "preview_url": preview_map.get(storage_path, ""),
                "net_a_payer": net_amount,
            }
        )
    return result


def get_employee_payslips(employee_id: str) -> list[dict[str, Any]]:
    """Liste des bulletins d'un employé (sans net_a_payer)."""
    r = (
        supabase.table("payslips")
        .select("id, month, year, pdf_storage_path")
        .eq("employee_id", employee_id)
        .execute()
    )
    payslips_db = (r.data or []) if r else []
    if not payslips_db:
        return []

    paths = [p["pdf_storage_path"] for p in payslips_db if p.get("pdf_storage_path")]
    if not paths:
        return []

    download_map, preview_map = create_payslip_url_maps(paths, 3600)

    return [
        {
            "id": p["id"],
            "name": p["pdf_storage_path"].split("/")[-1],
            "month": p["month"],
            "year": p["year"],
            "url": download_map[p["pdf_storage_path"]],
            "preview_url": preview_map.get(p["pdf_storage_path"], ""),
        }
        for p in payslips_db
        if p.get("pdf_storage_path") in download_map
    ]


def get_payslip_details(payslip_id: str) -> dict[str, Any] | None:
    """Détail complet d'un bulletin (dont cumuls, url signée). Utilise le mapper pour la structure."""
    r = (
        supabase.table("payslips")
        .select("*")
        .eq("id", payslip_id)
        .single()
        .execute()
    )
    row = r.data if r else None
    if not row:
        return None

    signed_url = ""
    preview_url = ""
    storage_path = row.get("pdf_storage_path")
    if storage_path:
        signed_url, preview_url = create_payslip_signed_urls(storage_path, 3600)

    cumuls = None
    emp_id = row.get("employee_id")
    year = row.get("year")
    month = row.get("month")
    if emp_id is not None and year is not None and month is not None:
        cumuls_res = (
            supabase.table("employee_schedules")
            .select("cumuls")
            .match({"employee_id": emp_id, "year": year, "month": month})
            .maybe_single()
            .execute()
        )
        cumuls = (
            (cumuls_res.data or {}).get("cumuls")
            if cumuls_res and cumuls_res.data
            else None
        )

    return build_payslip_detail(row, signed_url, cumuls, preview_url)


def get_payslip_history(payslip_id: str) -> list[dict[str, Any]]:
    """Historique d'édition d'un bulletin."""
    r = (
        supabase.table("payslips")
        .select("edit_history")
        .eq("id", payslip_id)
        .single()
        .execute()
    )
    payslip = r.data if r else None
    if not payslip:
        return []
    history = payslip.get("edit_history")
    return history if isinstance(history, list) else []
