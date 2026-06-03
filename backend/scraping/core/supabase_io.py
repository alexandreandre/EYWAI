"""Persistance payroll_config (versioning, rollback, cotisations)."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from cotisation_sync import persist_cotisations_config
from supabase import Client, create_client

logger = logging.getLogger(__name__)


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_supabase_client() -> Client:
    url = os.environ.get("SUPABASE_URL")
    if not url:
        raise EnvironmentError("SUPABASE_URL manquant dans .env")

    candidates = [
        k
        for k in (
            os.environ.get("SUPABASE_SERVICE_ROLE_KEY"),
            os.environ.get("SUPABASE_SERVICE_KEY"),
            os.environ.get("SUPABASE_KEY"),
        )
        if k
    ]

    def _jwt_role(jwt: str) -> str | None:
        import base64
        import json as _json

        try:
            parts = jwt.split(".")
            if len(parts) < 2:
                return None
            pad = "=" * (-len(parts[1]) % 4)
            payload = _json.loads(base64.urlsafe_b64decode(parts[1] + pad))
            return payload.get("role")
        except Exception:
            return None

    key = next((k for k in candidates if _jwt_role(k) == "service_role"), None)
    if not key:
        key = candidates[0] if candidates else None
    if not key:
        raise EnvironmentError(
            "Clé Supabase admin manquante (SUPABASE_SERVICE_ROLE_KEY / SUPABASE_KEY)."
        )
    return create_client(url, key)


def fetch_active_config(supabase: Client, config_key: str) -> Optional[Dict[str, Any]]:
    logger.info("Lecture config active: %s", config_key)
    response = (
        supabase.table("payroll_config")
        .select("*")
        .eq("config_key", config_key)
        .eq("is_active", True)
        .maybe_single()
        .execute()
    )
    if response is None:
        return None
    return response.data


def persist_full_config(
    supabase: Client,
    *,
    config_key: str,
    new_config_data: Dict[str, Any],
    source_links: List[str],
    comment: str,
    current_row: Optional[Dict[str, Any]] = None,
) -> None:
    """Remplace ou versionne un bloc config_data entier."""
    if current_row is None:
        current_row = fetch_active_config(supabase, config_key)

    if current_row is None:
        row = {
            "config_key": config_key,
            "config_data": new_config_data,
            "version": 1,
            "is_active": True,
            "comment": comment,
            "last_checked_at": iso_now(),
            "source_links": source_links,
        }
        supabase.table("payroll_config").insert(row).execute()
        logger.info("Config %s v1 créée", config_key)
        return

    current_id = current_row["id"]
    current_version = current_row["version"]
    current_data = current_row["config_data"]

    if current_data == new_config_data:
        supabase.table("payroll_config").update(
            {"last_checked_at": iso_now(), "source_links": source_links}
        ).eq("id", current_id).execute()
        logger.info("Config %s inchangée — last_checked_at mis à jour", config_key)
        return

    new_row = {
        "config_key": config_key,
        "config_data": new_config_data,
        "version": current_version + 1,
        "is_active": True,
        "comment": comment,
        "last_checked_at": iso_now(),
        "source_links": source_links,
    }
    try:
        supabase.table("payroll_config").update({"is_active": False}).eq(
            "id", current_id
        ).execute()
        supabase.table("payroll_config").insert(new_row).execute()
        logger.info("Config %s → v%s", config_key, current_version + 1)
    except Exception:
        logger.warning("Rollback: réactivation v%s", current_version)
        supabase.table("payroll_config").update({"is_active": True}).eq(
            "id", current_id
        ).execute()
        raise


def touch_last_checked_at(
    supabase: Client,
    *,
    config_key: str,
    persistence_mode: str,
    current_row: Optional[Dict[str, Any]],
    source_links: Optional[List[str]] = None,
) -> None:
    """Horodate un contrôle réussi sans modifier les taux (gate validation humaine, etc.)."""
    import copy

    from cotisation_sync import is_full_cotisations_sync, stamp_cotisation_inplace

    if not current_row:
        return

    now = iso_now()
    current_id = current_row["id"]

    if persistence_mode == "cotisations" or config_key == "cotisations":
        config_data = copy.deepcopy(current_row.get("config_data") or {})
        items = config_data.get("cotisations")
        if not isinstance(items, list):
            return
        for item in items:
            if isinstance(item, dict) and item.get("id"):
                stamp_cotisation_inplace(item, str(item["id"]))
        payload: Dict[str, Any] = {"config_data": config_data}
        if source_links is not None:
            payload["source_links"] = source_links
        if is_full_cotisations_sync():
            payload["last_checked_at"] = now
        supabase.table("payroll_config").update(payload).eq("id", current_id).execute()
        logger.info("Contrôle cotisations — horodatages mis à jour")
        return

    payload: Dict[str, Any] = {"last_checked_at": now}
    if source_links is not None:
        payload["source_links"] = source_links
    supabase.table("payroll_config").update(payload).eq("id", current_id).execute()
    logger.info("Contrôle %s — last_checked_at mis à jour", config_key)


def persist_cotisations(
    supabase: Client,
    *,
    new_config_data: Dict[str, Any],
    source_links: List[str],
    comment: str,
    current_row: Optional[Dict[str, Any]] = None,
) -> None:
    if current_row is None:
        current_row = fetch_active_config(supabase, "cotisations")
    persist_cotisations_config(
        supabase, current_row, new_config_data, source_links, comment
    )


def emit_orchestrator_result(
    *,
    scraper: str,
    success: bool,
    config_key: str,
    data: Dict[str, Any],
    sources_used: List[str],
    error: str = "",
    warnings: List[str] | None = None,
    decision_case: Optional[str] = None,
    sources_agreement: Optional[bool] = None,
    discrepancies: Optional[List[Dict[str, Any]]] = None,
    current_value: Optional[Dict[str, Any]] = None,
    proposed_value: Optional[Dict[str, Any]] = None,
    ai_candidate: Optional[Dict[str, Any]] = None,
    tier: Optional[str] = None,
    requires_review: Optional[bool] = None,
) -> None:
    out: Dict[str, Any] = {
        "scraper": scraper,
        "success": success,
        "timestamp": iso_now(),
        "config_key": config_key,
    }
    if warnings:
        out["warnings"] = warnings
    if success:
        out["data"] = data
        out["sources_used"] = sources_used
    else:
        out["error"] = error
        out["data"] = {}

    # Métadonnées de décision v2 (validation humaine / tripwire).
    if decision_case is not None:
        out["decision_case"] = decision_case
    if sources_agreement is not None:
        out["sources_agreement"] = sources_agreement
    if discrepancies is not None:
        out["discrepancies"] = discrepancies
    if current_value is not None:
        out["current_value"] = current_value
    if proposed_value is not None:
        out["proposed_value"] = proposed_value
    if ai_candidate is not None:
        out["ai_candidate"] = ai_candidate
    if tier is not None:
        out["tier"] = tier
    if requires_review is not None:
        out["requires_review"] = requires_review

    print(json.dumps(out, ensure_ascii=False))
