"""Persistance import admin."""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, List, Optional, Tuple

from postgrest.exceptions import APIError

from app.core.database import get_supabase_admin_client
from app.core.logging import get_logger

logger = get_logger("modules.admin_import.infrastructure.repository")

_EMPLOYEE_BASE_COLUMNS = (
    "id, first_name, last_name, email, nir, coordonnees_bancaires, "
    "employment_status, employee_folder_name, sexe"
)


def _normalize_siret(value: Optional[str]) -> str:
    return re.sub(r"\s", "", str(value or ""))


def _normalize_company_name(value: Optional[str]) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]", "", text.lower())


def find_company_by_siret(siret: str) -> Optional[Dict[str, Any]]:
    clean = _normalize_siret(siret)
    if not clean:
        return None
    try:
        client = get_supabase_admin_client()
        resp = (
            client.table("companies")
            .select("id, company_name, siret, siren")
            .eq("siret", clean)
            .limit(1)
            .execute()
        )
        if resp.data:
            return resp.data[0]
        if len(clean) >= 9:
            siren = clean[:9]
            by_siren = (
                client.table("companies")
                .select("id, company_name, siret, siren")
                .eq("siren", siren)
                .limit(2)
                .execute()
            )
            if len(by_siren.data or []) == 1:
                return by_siren.data[0]
    except Exception:
        logger.exception("Recherche entreprise SIRET %s échouée", siret)
        return None
    return None


def find_company_by_normalized_name(company_name: str) -> Optional[Dict[str, Any]]:
    target = _normalize_company_name(company_name)
    if not target:
        return None
    try:
        client = get_supabase_admin_client()
        resp = (
            client.table("companies")
            .select("id, company_name, siret, siren")
            .eq("is_active", True)
            .execute()
        )
        companies = resp.data or []
        exact = [
            c
            for c in companies
            if _normalize_company_name(c.get("company_name")) == target
        ]
        if len(exact) == 1:
            return exact[0]
        if len(exact) > 1:
            return None
        partial = [
            c
            for c in companies
            if target in _normalize_company_name(c.get("company_name"))
            or _normalize_company_name(c.get("company_name")) in target
        ]
        if len(partial) == 1:
            return partial[0]
    except Exception:
        logger.exception("Recherche entreprise par nom %s échouée", company_name)
        return None
    return None


def resolve_company_from_payslip(
    siret: Optional[str],
    company_name: Optional[str],
) -> Tuple[Optional[Dict[str, Any]], List[str]]:
    """Résout une entreprise depuis SIRET, SIREN ou nom bulletin."""
    warnings: List[str] = []
    clean_siret = _normalize_siret(siret)

    if clean_siret:
        company = find_company_by_siret(clean_siret)
        if company:
            return company, warnings

    if company_name:
        company = find_company_by_normalized_name(company_name)
        if company:
            stored_siret = _normalize_siret(company.get("siret"))
            if clean_siret and not stored_siret:
                warnings.append(
                    f"Entreprise identifiée par nom « {company_name.strip()} » "
                    f"(SIRET {clean_siret} non enregistré dans EYWAI)."
                )
            elif clean_siret and stored_siret and stored_siret != clean_siret:
                warnings.append(
                    f"Entreprise identifiée par nom ; SIRET bulletin ({clean_siret}) "
                    f"diffère du SIRET enregistré ({stored_siret})."
                )
            return company, warnings

    if clean_siret:
        warnings.append(f"Entreprise SIRET {clean_siret} introuvable dans EYWAI.")

    return None, warnings


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
            .select("id, company_name, idcc")
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
