"""Persistance import admin."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from postgrest.exceptions import APIError

from app.core.database import get_supabase_admin_client
from app.core.logging import get_logger

logger = get_logger("modules.admin_import.infrastructure.repository")

_EMPLOYEE_BASE_COLUMNS = (
    "id, first_name, last_name, email, coordonnees_bancaires, "
    "employment_status, employee_folder_name"
)


def find_company_by_siret(siret: str) -> Optional[Dict[str, Any]]:
    if not siret:
        return None
    try:
        client = get_supabase_admin_client()
        resp = (
            client.table("companies")
            .select("id, company_name, siret")
            .eq("siret", siret)
            .limit(1)
            .execute()
        )
        return resp.data[0] if resp.data else None
    except Exception:
        logger.exception("Recherche entreprise SIRET %s échouée", siret)
        return None


def list_employees_by_company_ids(
    company_ids: List[str],
) -> Dict[str, List[Dict[str, Any]]]:
    """Retourne {company_id: [employees]} pour plusieurs entreprises."""
    if not company_ids:
        return {}
    result: Dict[str, List[Dict[str, Any]]] = {cid: [] for cid in company_ids}
    for company_id in company_ids:
        result[company_id] = list_company_employees(company_id)
    return result


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
    """Liste tous les salariés actifs ou non d'une entreprise (pagination incluse)."""
    client = get_supabase_admin_client()
    columns = _EMPLOYEE_BASE_COLUMNS
    try:
        probe = (
            client.table("employees")
            .select(f"{columns}, time_tracking_id")
            .eq("company_id", company_id)
            .limit(1)
            .execute()
        )
        if probe.data is not None:
            columns = f"{columns}, time_tracking_id"
    except APIError:
        pass
    except Exception:
        logger.exception("Probe colonnes employees échouée")

    out: List[Dict[str, Any]] = []
    page_size = 500
    offset = 0
    try:
        while True:
            resp = (
                client.table("employees")
                .select(columns)
                .eq("company_id", company_id)
                .order("last_name")
                .range(offset, offset + page_size - 1)
                .execute()
            )
            batch = resp.data or []
            if not batch:
                break
            out.extend(batch)
            if len(batch) < page_size:
                break
            offset += page_size
    except Exception:
        logger.exception("Liste employés entreprise %s échouée", company_id)
        return []
    return out


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
