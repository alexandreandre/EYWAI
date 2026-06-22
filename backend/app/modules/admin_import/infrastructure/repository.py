"""Persistance import admin."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.core.database import get_supabase_admin_client
from app.core.logging import get_logger

logger = get_logger("modules.admin_import.infrastructure.repository")


def find_company(company_id: str) -> Optional[Dict[str, Any]]:
    try:
        client = get_supabase_admin_client()
        resp = (
            client.table("companies")
            .select("id, company_name")
            .eq("id", company_id)
            .limit(1)
            .execute()
        )
        return resp.data[0] if resp.data else None
    except Exception:
        logger.exception("Recherche entreprise %s échouée", company_id)
        return None


def list_company_employees(company_id: str) -> List[Dict[str, Any]]:
    try:
        client = get_supabase_admin_client()
        resp = (
            client.table("employees")
            .select(
                "id, first_name, last_name, email, time_tracking_id, coordonnees_bancaires, employment_status"
            )
            .eq("company_id", company_id)
            .order("last_name")
            .execute()
        )
        return resp.data or []
    except Exception:
        logger.exception("Liste employés entreprise %s échouée", company_id)
        return []


def update_employee_rib(employee_id: str, coordonnees: Dict[str, Any]) -> bool:
    try:
        client = get_supabase_admin_client()
        resp = (
            client.table("employees")
            .update({"coordonnees_bancaires": coordonnees})
            .eq("id", employee_id)
            .execute()
        )
        return bool(resp.data)
    except Exception:
        logger.exception("Mise à jour RIB employé %s échouée", employee_id)
        return False
