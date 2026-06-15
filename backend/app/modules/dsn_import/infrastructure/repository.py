"""Persistance Supabase pour l'import DSN."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.core.database import get_supabase_admin_client
from app.core.logging import get_logger

logger = get_logger("modules.dsn_import.repository")

BATCHES_TABLE = "dsn_import_batches"
ITEMS_TABLE = "dsn_import_items"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def insert_batch(record: Dict[str, Any]) -> Optional[str]:
    try:
        client = get_supabase_admin_client()
        resp = client.table(BATCHES_TABLE).insert(record).execute()
        if resp.data:
            return str(resp.data[0]["id"])
    except Exception:
        logger.exception("Insertion dsn_import_batches échouée")
    return None


def update_batch(batch_id: str, fields: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    client = get_supabase_admin_client()
    payload = {**fields, "updated_at": _now_iso()}
    resp = client.table(BATCHES_TABLE).update(payload).eq("id", batch_id).execute()
    return resp.data[0] if resp.data else None


def get_batch(batch_id: str) -> Optional[Dict[str, Any]]:
    try:
        client = get_supabase_admin_client()
        resp = client.table(BATCHES_TABLE).select("*").eq("id", batch_id).limit(1).execute()
        return resp.data[0] if resp.data else None
    except Exception:
        logger.exception("Lecture batch %s échouée", batch_id)
        return None


def list_batches(limit: int = 50) -> List[Dict[str, Any]]:
    try:
        client = get_supabase_admin_client()
        resp = (
            client.table(BATCHES_TABLE)
            .select("*")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return resp.data or []
    except Exception:
        logger.exception("Liste batches échouée")
        return []


def insert_items(items: List[Dict[str, Any]]) -> int:
    if not items:
        return 0
    try:
        client = get_supabase_admin_client()
        resp = client.table(ITEMS_TABLE).insert(items).execute()
        return len(resp.data or [])
    except Exception:
        logger.exception("Insertion dsn_import_items échouée")
        return 0


def list_items(batch_id: str) -> List[Dict[str, Any]]:
    try:
        client = get_supabase_admin_client()
        resp = (
            client.table(ITEMS_TABLE)
            .select("*")
            .eq("batch_id", batch_id)
            .order("created_at")
            .execute()
        )
        return resp.data or []
    except Exception:
        logger.exception("Liste items batch %s échouée", batch_id)
        return []


def update_item(item_id: str, fields: Dict[str, Any]) -> None:
    try:
        client = get_supabase_admin_client()
        client.table(ITEMS_TABLE).update({**fields, "updated_at": _now_iso()}).eq(
            "id", item_id
        ).execute()
    except Exception:
        logger.exception("MAJ item %s échouée", item_id)


def find_group_by_siren(siren: str) -> Optional[Dict[str, Any]]:
    if not siren:
        return None
    try:
        client = get_supabase_admin_client()
        resp = (
            client.table("company_groups")
            .select("*")
            .eq("siren", siren)
            .limit(1)
            .execute()
        )
        return resp.data[0] if resp.data else None
    except Exception:
        logger.exception("Recherche groupe SIREN %s échouée", siren)
        return None


def find_company_by_siret(siret: str) -> Optional[Dict[str, Any]]:
    if not siret:
        return None
    try:
        client = get_supabase_admin_client()
        resp = (
            client.table("companies")
            .select("*")
            .eq("siret", siret)
            .limit(1)
            .execute()
        )
        return resp.data[0] if resp.data else None
    except Exception:
        logger.exception("Recherche entreprise SIRET %s échouée", siret)
        return None


def find_employee_by_nir(company_id: str, nir: str) -> Optional[Dict[str, Any]]:
    if not company_id or not nir:
        return None
    try:
        client = get_supabase_admin_client()
        resp = (
            client.table("employees")
            .select("*")
            .eq("company_id", company_id)
            .eq("nir", nir)
            .limit(1)
            .execute()
        )
        return resp.data[0] if resp.data else None
    except Exception:
        logger.exception("Recherche salarié NIR échouée")
        return None


def resolve_collective_agreement_id(idcc: str) -> Optional[str]:
    if not idcc:
        return None
    try:
        client = get_supabase_admin_client()
        resp = (
            client.table("collective_agreements_catalog")
            .select("id")
            .eq("idcc", idcc.strip())
            .limit(1)
            .execute()
        )
        return str(resp.data[0]["id"]) if resp.data else None
    except Exception:
        logger.exception("Recherche IDCC %s échouée", idcc)
        return None


def upsert_company_collective_agreement(company_id: str, agreement_id: str) -> None:
    try:
        client = get_supabase_admin_client()
        existing = (
            client.table("company_collective_agreements")
            .select("id")
            .eq("company_id", company_id)
            .eq("collective_agreement_id", agreement_id)
            .limit(1)
            .execute()
        )
        if existing.data:
            return
        client.table("company_collective_agreements").insert(
            {"company_id": company_id, "collective_agreement_id": agreement_id}
        ).execute()
    except Exception:
        logger.exception("Assignation CC entreprise échouée")
