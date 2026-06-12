"""Accès Supabase pour company_accounting_config, catalogue plateforme et transmissions."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.core.database import get_supabase_admin_client
from app.core.logging import get_logger

logger = get_logger("modules.accounting_integration.repository")

_SCHEMA_MISSING_LOGGED: set[str] = set()


def _is_schema_missing(exc: Exception) -> bool:
    msg = str(exc)
    return "PGRST205" in msg or "Could not find the table" in msg


def _log_db_error(context: str, exc: Exception) -> None:
    if _is_schema_missing(exc):
        if context not in _SCHEMA_MISSING_LOGGED:
            _SCHEMA_MISSING_LOGGED.add(context)
            logger.warning(
                "%s : tables compta absentes — appliquer la migration "
                "supabase/migrations/20260611210000_accounting_integrations.sql",
                context,
            )
        return
    logger.exception(context)


CONFIG_TABLE = "company_accounting_config"
PLATFORM_TABLE = "platform_accounting_providers"
TRANSMISSIONS_TABLE = "accounting_transmissions"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_config(company_id: str) -> Optional[Dict[str, Any]]:
    try:
        client = get_supabase_admin_client()
        resp = (
            client.table(CONFIG_TABLE)
            .select("*")
            .eq("company_id", company_id)
            .limit(1)
            .execute()
        )
        if resp.data:
            return resp.data[0]
    except Exception as exc:
        _log_db_error(f"Lecture config compta échouée (company={company_id})", exc)
    return None


def upsert_config(company_id: str, fields: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    client = get_supabase_admin_client()
    existing = get_config(company_id)
    payload = {k: v for k, v in fields.items()}
    payload["updated_at"] = _now_iso()
    if existing:
        resp = (
            client.table(CONFIG_TABLE)
            .update(payload)
            .eq("company_id", company_id)
            .execute()
        )
    else:
        payload["company_id"] = company_id
        payload.setdefault("created_at", _now_iso())
        resp = client.table(CONFIG_TABLE).insert(payload).execute()
    if resp.data:
        return resp.data[0] if isinstance(resp.data, list) else resp.data
    return get_config(company_id)


def list_platform_providers() -> List[Dict[str, Any]]:
    try:
        client = get_supabase_admin_client()
        resp = client.table(PLATFORM_TABLE).select("*").order("provider_key").execute()
        return list(resp.data or [])
    except Exception as exc:
        _log_db_error("Lecture catalogue plateforme compta échouée", exc)
        return []


def get_platform_provider(provider_key: str) -> Optional[Dict[str, Any]]:
    try:
        client = get_supabase_admin_client()
        resp = (
            client.table(PLATFORM_TABLE)
            .select("*")
            .eq("provider_key", provider_key)
            .limit(1)
            .execute()
        )
        if resp.data:
            return resp.data[0]
    except Exception as exc:
        _log_db_error(f"Lecture provider plateforme {provider_key} échouée", exc)
    return None


def upsert_platform_provider(
    provider_key: str, fields: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    client = get_supabase_admin_client()
    existing = get_platform_provider(provider_key)
    payload = {**fields, "updated_at": _now_iso()}
    if existing:
        resp = (
            client.table(PLATFORM_TABLE)
            .update(payload)
            .eq("provider_key", provider_key)
            .execute()
        )
    else:
        payload["provider_key"] = provider_key
        payload.setdefault("created_at", _now_iso())
        resp = client.table(PLATFORM_TABLE).insert(payload).execute()
    if resp.data:
        row = resp.data[0] if isinstance(resp.data, list) else resp.data
        return row
    return get_platform_provider(provider_key)


def insert_transmission(record: Dict[str, Any]) -> Optional[str]:
    try:
        client = get_supabase_admin_client()
        payload = {**record, "created_at": record.get("created_at") or _now_iso()}
        resp = client.table(TRANSMISSIONS_TABLE).insert(payload).execute()
        if resp.data:
            row = resp.data[0] if isinstance(resp.data, list) else resp.data
            return str(row.get("id"))
    except Exception as exc:
        _log_db_error(
            f"Insertion accounting_transmissions échouée (company={record.get('company_id')})",
            exc,
        )
    return None


def update_transmission(transmission_id: str, fields: Dict[str, Any]) -> None:
    try:
        client = get_supabase_admin_client()
        client.table(TRANSMISSIONS_TABLE).update(
            {**fields, "updated_at": _now_iso()}
        ).eq("id", transmission_id).execute()
    except Exception as exc:
        _log_db_error(f"MAJ transmission {transmission_id} échouée", exc)


def get_transmission(transmission_id: str) -> Optional[Dict[str, Any]]:
    try:
        client = get_supabase_admin_client()
        resp = (
            client.table(TRANSMISSIONS_TABLE)
            .select("*")
            .eq("id", transmission_id)
            .limit(1)
            .execute()
        )
        if resp.data:
            return resp.data[0]
    except Exception as exc:
        _log_db_error(f"Lecture transmission {transmission_id} échouée", exc)
    return None


def list_transmissions(
    company_id: Optional[str] = None,
    *,
    period: Optional[str] = None,
    status: Optional[str] = None,
    provider: Optional[str] = None,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    try:
        client = get_supabase_admin_client()
        q = client.table(TRANSMISSIONS_TABLE).select("*").order("created_at", desc=True)
        if company_id:
            q = q.eq("company_id", company_id)
        if period:
            q = q.eq("period", period)
        if status:
            q = q.eq("status", status)
        if provider:
            q = q.eq("provider", provider)
        resp = q.limit(limit).execute()
        return list(resp.data or [])
    except Exception as exc:
        _log_db_error("Liste transmissions compta échouée", exc)
        return []


def find_existing_transmission(
    company_id: str, period: str, channel: str
) -> Optional[Dict[str, Any]]:
    try:
        client = get_supabase_admin_client()
        resp = (
            client.table(TRANSMISSIONS_TABLE)
            .select("*")
            .eq("company_id", company_id)
            .eq("period", period)
            .eq("channel", channel)
            .in_("status", ["sent", "acknowledged", "queued", "transmitted"])
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        if resp.data:
            return resp.data[0]
    except Exception as exc:
        _log_db_error("Recherche transmission existante échouée", exc)
    return None
