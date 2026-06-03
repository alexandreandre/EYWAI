#!/usr/bin/env python3
"""Applique un changement validé humainement à payroll_config.

Single-source de l'écriture : réutilise persist_full_config / persist_cotisations
(la logique de versioning immuable). Aucune réimplémentation du versioning ici.

Usage : python apply_pending_change.py <pending_id>
Le réviseur peut être transmis via EYWAI_REVIEWED_BY.
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

# Amorçage sys.path (comme les orchestrateurs) pour importer core.* / utils.
_SCRAPING = Path(__file__).resolve().parent.parent
if str(_SCRAPING) not in sys.path:
    sys.path.insert(0, str(_SCRAPING))

from core.env import ensure_scraping_path, load_env  # noqa: E402
from core.supabase_io import (  # noqa: E402
    fetch_active_config,
    init_supabase_client,
    persist_cotisations,
    persist_full_config,
)

logger = logging.getLogger(__name__)

PENDING_TABLE = "scraping_pending_changes"


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _fetch_pending(supabase, pending_id: str) -> Optional[Dict[str, Any]]:
    resp = (
        supabase.table(PENDING_TABLE)
        .select("*")
        .eq("id", pending_id)
        .maybe_single()
        .execute()
    )
    return resp.data if resp and resp.data else None


def apply_pending_change(pending_id: str, reviewed_by: Optional[str] = None) -> int:
    """Applique un pending. Retourne 0 si succès, code non nul sinon."""
    ensure_scraping_path()
    load_env()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] - %(message)s")

    supabase = init_supabase_client()
    pending = _fetch_pending(supabase, pending_id)
    if pending is None:
        logger.error("Changement en attente introuvable : %s", pending_id)
        return 2
    if pending.get("status") != "pending":
        logger.error(
            "Changement %s déjà traité (status=%s) — abandon.",
            pending_id,
            pending.get("status"),
        )
        return 3

    config_key = pending["config_key"]
    persistence_mode = pending.get("persistence_mode", "full")
    new_data = pending["proposed_config_data"]
    source_links = pending.get("source_links") or []
    comment = (
        f"Validé manuellement ({reviewed_by or 'super_admin'}) — {config_key}"
    )

    current_row = fetch_active_config(supabase, config_key)

    if persistence_mode == "cotisations":
        persist_cotisations(
            supabase,
            new_config_data=new_data,
            source_links=source_links,
            comment=comment,
            current_row=current_row,
        )
    else:
        persist_full_config(
            supabase,
            config_key=config_key,
            new_config_data=new_data,
            source_links=source_links,
            comment=comment,
            current_row=current_row,
        )

    applied_row = fetch_active_config(supabase, config_key)
    applied_id = applied_row.get("id") if applied_row else None

    supabase.table(PENDING_TABLE).update(
        {
            "status": "approved",
            "reviewed_at": _iso_now(),
            "reviewed_by": reviewed_by,
            "applied_at": _iso_now(),
            "applied_payroll_config_id": applied_id,
        }
    ).eq("id", pending_id).execute()

    logger.info("Changement %s appliqué à payroll_config (%s).", pending_id, config_key)
    return 0


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python apply_pending_change.py <pending_id>", file=sys.stderr)
        sys.exit(64)
    pending_id = sys.argv[1]
    reviewed_by = os.environ.get("EYWAI_REVIEWED_BY") or None
    sys.exit(apply_pending_change(pending_id, reviewed_by))


if __name__ == "__main__":
    main()
