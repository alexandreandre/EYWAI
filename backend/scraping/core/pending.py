"""Gate de validation humaine : staging des changements critiques.

Sur le tier `critical`, l'orchestrateur n'écrit jamais directement `payroll_config`.
Il dépose un changement en attente dans `scraping_pending_changes` ; un super admin
valide (ou rejette) depuis le dashboard, puis `apply_pending_change` applique le
changement via la logique de versioning existante.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from cotisation_sync import cotisations_rates_equal
from supabase import Client

logger = logging.getLogger(__name__)

PENDING_TABLE = "scraping_pending_changes"


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def config_changed(
    persistence_mode: str,
    current_row: Optional[Dict[str, Any]],
    new_config_data: Dict[str, Any],
) -> bool:
    """True si `new_config_data` modifie réellement la config active.

    Réutilise exactement les comparaisons de la couche de persistance :
    égalité brute en mode FULL, comparaison hors horodatage en mode COTISATIONS.
    """
    if current_row is None:
        return True
    current = current_row.get("config_data")
    if persistence_mode == "cotisations":
        return not cotisations_rates_equal(current or {}, new_config_data)
    return current != new_config_data


def extract_citation(payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Extrait la première citation (url + date) du `meta.source` d'un payload IA."""
    if not isinstance(payload, dict):
        return {}
    sources = payload.get("meta", {}).get("source", [])
    for src in sources:
        if isinstance(src, dict) and src.get("url"):
            return {
                "citation_url": src.get("url"),
                "citation_date": src.get("date_doc") or src.get("date") or "",
                "citation_label": src.get("label", ""),
            }
    return {}


def build_ai_candidate(
    labels: List[str],
    sigs: List[Any],
    payloads: List[Dict[str, Any]],
    *,
    is_ai: Callable[[str], bool],
) -> Optional[Dict[str, Any]]:
    """Construit la candidate IA (valeur + citation) à partir des sources IA valides."""
    for i, label in enumerate(labels):
        if not is_ai(label):
            continue
        candidate: Dict[str, Any] = {
            "label": label,
            "value": sigs[i] if i < len(sigs) else None,
        }
        citation = extract_citation(payloads[i] if i < len(payloads) else None)
        candidate.update(citation)
        return candidate
    return None


def resolve_source_id(supabase: Client, source_key: Optional[str]) -> Optional[str]:
    """Best-effort : retrouve scraping_sources.id à partir d'un source_key."""
    if not source_key:
        return None
    try:
        resp = (
            supabase.table("scraping_sources")
            .select("id")
            .eq("source_key", source_key)
            .limit(1)
            .execute()
        )
        if resp.data:
            return resp.data[0]["id"]
    except Exception as exc:  # pragma: no cover - dépend de la DB
        logger.warning("resolve_source_id(%s) a échoué: %s", source_key, exc)
    return None


def requires_human_gate(
    tier: str,
    changed: bool,
    decision_case: str,
    ai_divergence: bool,
) -> bool:
    """True si un tier critical doit passer par la validation humaine.

    Gate élargi (plan v2) : changement réel, cas B/C, ou IA divergente.
    """
    if tier != "critical":
        return False
    return changed or decision_case in ("B", "C") or ai_divergence


def get_last_approved_change(
    supabase: Client,
    config_key: str,
) -> Optional[Dict[str, Any]]:
    """Dernière validation humaine approuvée pour un config_key (vérité terrain)."""
    try:
        resp = (
            supabase.table(PENDING_TABLE)
            .select("*")
            .eq("config_key", config_key)
            .eq("status", "approved")
            .order("applied_at", desc=True)
            .limit(1)
            .execute()
        )
        return resp.data[0] if resp.data else None
    except Exception as exc:  # pragma: no cover
        logger.warning("get_last_approved_change(%s): %s", config_key, exc)
        return None


def create_pending_change(
    supabase: Client,
    *,
    scraper_name: str,
    config_key: str,
    tier: str,
    persistence_mode: str,
    proposed_config_data: Dict[str, Any],
    current_row: Optional[Dict[str, Any]],
    source_links: List[str],
    decision_case: str,
    sources_agreement: bool,
    discrepancies: List[Dict[str, Any]],
    ai_candidate: Optional[Dict[str, Any]],
    warnings: Optional[List[str]],
    source_id: Optional[str] = None,
    created_by_job_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Dépose un changement en attente. Les pending antérieurs du même config_key
    et scraper passent à `superseded` (un seul pending actif à la fois)."""
    try:
        supabase.table(PENDING_TABLE).update({"status": "superseded"}).eq(
            "config_key", config_key
        ).eq("scraper_name", scraper_name).eq("status", "pending").execute()
    except Exception as exc:  # pragma: no cover
        logger.warning("Supersede des pending %s a échoué: %s", config_key, exc)

    row: Dict[str, Any] = {
        "source_id": source_id,
        "scraper_name": scraper_name,
        "config_key": config_key,
        "tier": tier,
        "persistence_mode": persistence_mode,
        "proposed_config_data": proposed_config_data,
        "current_config_data": (current_row or {}).get("config_data"),
        "current_version": (current_row or {}).get("version"),
        "source_links": source_links,
        "decision_case": decision_case,
        "sources_agreement": sources_agreement,
        "discrepancies": discrepancies,
        "ai_candidate": ai_candidate,
        "warnings": warnings or [],
        "status": "pending",
        "created_by_job_id": created_by_job_id,
        "created_at": _iso_now(),
    }
    resp = supabase.table(PENDING_TABLE).insert(row).execute()
    logger.info(
        "Changement en attente créé pour %s (config_key=%s, cas=%s)",
        scraper_name,
        config_key,
        decision_case,
    )
    return resp.data[0] if resp.data else None
