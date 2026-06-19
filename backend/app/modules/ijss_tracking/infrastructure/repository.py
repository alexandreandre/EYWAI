"""Persistance Supabase — suivi IJSS."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.core.database import get_supabase_admin_client
from app.core.logging import get_logger

logger = get_logger("modules.ijss_tracking.repository")

PERIODS = "ijss_tracking_periods"
EXPECTED = "ijss_expected_lines"
RECEIVED = "ijss_received_lines"
BATCHES = "ijss_import_batches"
ITEMS = "ijss_import_items"
NOTES = "ijss_reconciliation_notes"
PROFILES = "company_ijss_import_profiles"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_or_create_period(
    company_id: str, year: int, month: int
) -> Optional[Dict[str, Any]]:
    client = get_supabase_admin_client()
    resp = (
        client.table(PERIODS)
        .select("*")
        .eq("company_id", company_id)
        .eq("period_year", year)
        .eq("period_month", month)
        .limit(1)
        .execute()
    )
    if resp.data:
        return resp.data[0]
    ins = (
        client.table(PERIODS)
        .insert(
            {
                "company_id": company_id,
                "period_year": year,
                "period_month": month,
                "status": "open",
            }
        )
        .execute()
    )
    return ins.data[0] if ins.data else None


def get_period(company_id: str, period_id: str) -> Optional[Dict[str, Any]]:
    try:
        resp = (
            get_supabase_admin_client()
            .table(PERIODS)
            .select("*")
            .eq("id", period_id)
            .eq("company_id", company_id)
            .limit(1)
            .execute()
        )
        return resp.data[0] if resp.data else None
    except Exception:
        logger.exception("Lecture période IJSS %s", period_id)
        return None


def update_period(period_id: str, fields: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    payload = {**fields, "updated_at": _now_iso()}
    resp = (
        get_supabase_admin_client()
        .table(PERIODS)
        .update(payload)
        .eq("id", period_id)
        .execute()
    )
    return resp.data[0] if resp.data else None


def list_expected_lines(period_id: str) -> List[Dict[str, Any]]:
    try:
        resp = (
            get_supabase_admin_client()
            .table(EXPECTED)
            .select("*")
            .eq("period_id", period_id)
            .execute()
        )
        return resp.data or []
    except Exception:
        logger.exception("Liste expected lines période %s", period_id)
        return []


def upsert_expected_line(record: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    client = get_supabase_admin_client()
    existing = (
        client.table(EXPECTED)
        .select("id")
        .eq("company_id", record["company_id"])
        .eq("employee_id", record["employee_id"])
        .eq("absence_request_id", record.get("absence_request_id"))
        .eq("period_year", record["period_year"])
        .eq("period_month", record["period_month"])
        .limit(1)
        .execute()
    )
    payload = {**record, "updated_at": _now_iso()}
    if existing.data:
        resp = (
            client.table(EXPECTED)
            .update(payload)
            .eq("id", existing.data[0]["id"])
            .execute()
        )
    else:
        resp = client.table(EXPECTED).insert(payload).execute()
    return resp.data[0] if resp.data else None


def get_expected_line(company_id: str, line_id: str) -> Optional[Dict[str, Any]]:
    try:
        resp = (
            get_supabase_admin_client()
            .table(EXPECTED)
            .select("*")
            .eq("id", line_id)
            .eq("company_id", company_id)
            .limit(1)
            .execute()
        )
        return resp.data[0] if resp.data else None
    except Exception:
        logger.exception("Lecture expected line %s", line_id)
        return None


def update_expected_line(
    line_id: str, fields: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    payload = {**fields, "updated_at": _now_iso()}
    resp = (
        get_supabase_admin_client()
        .table(EXPECTED)
        .update(payload)
        .eq("id", line_id)
        .execute()
    )
    return resp.data[0] if resp.data else None


def list_received_lines(period_id: str) -> List[Dict[str, Any]]:
    try:
        resp = (
            get_supabase_admin_client()
            .table(RECEIVED)
            .select("*")
            .eq("period_id", period_id)
            .execute()
        )
        return resp.data or []
    except Exception:
        logger.exception("Liste received lines période %s", period_id)
        return []


def insert_received_line(record: Dict[str, Any]) -> Optional[str]:
    try:
        resp = get_supabase_admin_client().table(RECEIVED).insert(record).execute()
        if resp.data:
            return str(resp.data[0]["id"])
    except Exception:
        logger.exception("Insertion received line échouée")
    return None


def update_received_line(line_id: str, fields: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    payload = {**fields, "updated_at": _now_iso()}
    resp = (
        get_supabase_admin_client()
        .table(RECEIVED)
        .update(payload)
        .eq("id", line_id)
        .execute()
    )
    return resp.data[0] if resp.data else None


def get_received_line(company_id: str, line_id: str) -> Optional[Dict[str, Any]]:
    try:
        resp = (
            get_supabase_admin_client()
            .table(RECEIVED)
            .select("*")
            .eq("id", line_id)
            .eq("company_id", company_id)
            .limit(1)
            .execute()
        )
        return resp.data[0] if resp.data else None
    except Exception:
        return None


def insert_batch(record: Dict[str, Any]) -> Optional[str]:
    try:
        resp = get_supabase_admin_client().table(BATCHES).insert(record).execute()
        if resp.data:
            return str(resp.data[0]["id"])
    except Exception:
        logger.exception("Insertion batch IJSS échouée")
    return None


def update_batch(batch_id: str, fields: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    payload = {**fields, "updated_at": _now_iso()}
    resp = (
        get_supabase_admin_client()
        .table(BATCHES)
        .update(payload)
        .eq("id", batch_id)
        .execute()
    )
    return resp.data[0] if resp.data else None


def get_batch(company_id: str, batch_id: str) -> Optional[Dict[str, Any]]:
    try:
        resp = (
            get_supabase_admin_client()
            .table(BATCHES)
            .select("*")
            .eq("id", batch_id)
            .eq("company_id", company_id)
            .limit(1)
            .execute()
        )
        return resp.data[0] if resp.data else None
    except Exception:
        return None


def insert_import_items(items: List[Dict[str, Any]]) -> None:
    if not items:
        return
    try:
        get_supabase_admin_client().table(ITEMS).insert(items).execute()
    except Exception:
        logger.exception("Insertion items import IJSS échouée")


def list_import_items(batch_id: str) -> List[Dict[str, Any]]:
    try:
        resp = (
            get_supabase_admin_client()
            .table(ITEMS)
            .select("*")
            .eq("batch_id", batch_id)
            .order("row_index")
            .execute()
        )
        return resp.data or []
    except Exception:
        return []


def insert_note(record: Dict[str, Any]) -> Optional[str]:
    try:
        resp = get_supabase_admin_client().table(NOTES).insert(record).execute()
        if resp.data:
            return str(resp.data[0]["id"])
    except Exception:
        logger.exception("Insertion note réconciliation échouée")
    return None


def list_notes_for_expected(expected_line_id: str) -> List[Dict[str, Any]]:
    try:
        resp = (
            get_supabase_admin_client()
            .table(NOTES)
            .select("*")
            .eq("expected_line_id", expected_line_id)
            .order("created_at")
            .execute()
        )
        return resp.data or []
    except Exception:
        return []


def get_import_profile(
    company_id: str, batch_type: str, profile_name: str = "default"
) -> Optional[Dict[str, Any]]:
    try:
        resp = (
            get_supabase_admin_client()
            .table(PROFILES)
            .select("*")
            .eq("company_id", company_id)
            .eq("batch_type", batch_type)
            .eq("profile_name", profile_name)
            .limit(1)
            .execute()
        )
        return resp.data[0] if resp.data else None
    except Exception:
        return None


def upsert_import_profile(
    company_id: str, batch_type: str, column_mapping: Dict[str, Any]
) -> None:
    client = get_supabase_admin_client()
    existing = get_import_profile(company_id, batch_type)
    payload = {
        "column_mapping": column_mapping,
        "updated_at": _now_iso(),
    }
    if existing:
        client.table(PROFILES).update(payload).eq("id", existing["id"]).execute()
    else:
        client.table(PROFILES).insert(
            {
                "company_id": company_id,
                "batch_type": batch_type,
                "profile_name": "default",
                "column_mapping": column_mapping,
            }
        ).execute()


def batch_exists_by_hash(company_id: str, file_hash: str) -> bool:
    try:
        resp = (
            get_supabase_admin_client()
            .table(BATCHES)
            .select("id")
            .eq("company_id", company_id)
            .eq("file_hash", file_hash)
            .eq("status", "committed")
            .limit(1)
            .execute()
        )
        return bool(resp.data)
    except Exception:
        return False
