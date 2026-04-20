"""Requêtes Supabase — signatures en attente (lecture annual_reviews)."""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from app.core.database import supabase

# Colonnes optionnelles (title, expires_at, last_reminder_at) : repli si schéma plus ancien.
_SELECT_FULL = (
    "id, title, year, interview_type, employee_id, signature_status, "
    "yousign_procedure_id, signed_pdf_url, created_at, updated_at, "
    "expires_at, last_reminder_at, "
    "employees(id, first_name, last_name)"
)

_SELECT_MIN = (
    "id, year, interview_type, employee_id, signature_status, "
    "yousign_procedure_id, signed_pdf_url, created_at, updated_at, "
    "employees(id, first_name, last_name)"
)


def _list_pending_rows(
    company_id: str,
    extra_filters: Dict[str, Any],
) -> List[Dict[str, Any]]:
    def _run(select_str: str) -> List[Dict[str, Any]]:
        q = (
            supabase.table("annual_reviews")
            .select(select_str)
            .eq("company_id", company_id)
            .eq("signature_status", "pending")
        )
        for key, val in extra_filters.items():
            q = q.eq(key, val)
        r = q.order("created_at", desc=False).execute()
        return (r.data or []) if r else []

    try:
        return _run(_SELECT_FULL)
    except Exception:
        return _run(_SELECT_MIN)


def get_pending_signatures_rh(company_id: str) -> List[Dict[str, Any]]:
    """
    Retourne toutes les procédures annual_reviews avec
    signature_status = 'pending' pour l'entreprise active.
    Jointure : employees(id, first_name, last_name)
    """
    return _list_pending_rows(company_id, {})


def get_pending_signatures_employee(
    employee_id: str, company_id: str
) -> List[Dict[str, Any]]:
    """
    Retourne les procédures où le salarié connecté
    est le signataire en attente.
    """
    return _list_pending_rows(company_id, {"employee_id": employee_id})


def get_yousign_config(company_id: str) -> Optional[Dict[str, Any]]:
    """
    Vérifie si Yousign est configuré pour l'entreprise (table yousign_configs ou équivalent).
    Repli : clé API globale YOUSIGN_API_KEY → considéré comme configuré (sans ligne BDD).
    Retourne None seulement si ni table/ligne ni variable d'environnement.
    """
    try:
        r = (
            supabase.table("yousign_configs")
            .select("id, company_id")
            .eq("company_id", company_id)
            .maybe_single()
            .execute()
        )
        row = r.data if r else None
        if row and isinstance(row, dict):
            return dict(row)
    except Exception:
        pass
    if os.getenv("YOUSIGN_API_KEY", "").strip():
        return {"id": "env", "company_id": company_id}
    return None


def get_annual_review_by_id(review_id: str) -> Optional[Dict[str, Any]]:
    """Charge une ligne annual_reviews par identifiant (sans filtre entreprise)."""
    r = (
        supabase.table("annual_reviews")
        .select(
            "id, company_id, employee_id, signature_status, yousign_procedure_id, "
            "created_at, updated_at"
        )
        .eq("id", review_id)
        .maybe_single()
        .execute()
    )
    row = r.data if r else None
    if not row or not isinstance(row, dict):
        return None
    return dict(row)


def update_review_reminder_timestamp(review_id: str, reminded_iso: str) -> None:
    """
    Met à jour last_reminder_at si la colonne existe, sinon updated_at seulement.
    """
    try:
        supabase.table("annual_reviews").update({"last_reminder_at": reminded_iso}).eq(
            "id", review_id
        ).execute()
    except Exception:
        supabase.table("annual_reviews").update({"updated_at": reminded_iso}).eq(
            "id", review_id
        ).execute()
