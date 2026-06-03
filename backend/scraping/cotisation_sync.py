"""
Horodatage et persistance des cotisations selon la cible de sync (EYWAI_SYNC_COTISATION_IDS).

Quand l'utilisateur met à jour une seule cotisation (ex. AGS), seule cette ligne reçoit
un last_checked_at dans config_data — pas les autres groupes (Brut, CET, etc.).
"""

from __future__ import annotations

import copy
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from supabase import Client

ENV_SYNC_COTISATION_IDS = "EYWAI_SYNC_COTISATION_IDS"
CONFIG_KEY_COTISATIONS = "cotisations"

# Clé de sync UI (Rates) -> ids présents dans config_data.cotisations
SYNC_TARGET_ALIASES: dict[str, set[str]] = {
    "vieillesse_patronal": {"retraite_secu_plafond", "retraite_secu_deplafond"},
    "vieillesse_salarial": {"retraite_secu_plafond", "retraite_secu_deplafond"},
    "cfp": {"CFP"},
    "CFP": {"CFP"},
    "csa": {"csa"},
    "CSA": {"csa"},
}


def iso_now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_sync_cotisation_ids() -> Optional[Set[str]]:
    """None = sync large (toutes les lignes patchées sont horodatées)."""
    raw = os.environ.get(ENV_SYNC_COTISATION_IDS, "").strip()
    if not raw:
        return None
    ids = {part.strip() for part in raw.split(",") if part.strip()}
    return ids or None


def is_full_cotisations_sync() -> bool:
    return parse_sync_cotisation_ids() is None


def _expanded_sync_targets(targets: Optional[Set[str]]) -> Optional[Set[str]]:
    if targets is None:
        return None
    expanded: Set[str] = set()
    for key in targets:
        expanded.add(key)
        expanded.update(SYNC_TARGET_ALIASES.get(key, set()))
    return expanded


def should_stamp_cotisation(cotisation_id: str) -> bool:
    targets = _expanded_sync_targets(parse_sync_cotisation_ids())
    if targets is None:
        return True
    return cotisation_id in targets


def should_apply_cotisation_patch(cotisation_id: str) -> bool:
    """True si les taux de cette ligne doivent être écrits lors de la sync en cours."""
    return should_stamp_cotisation(cotisation_id)


def merge_cotisation_item(
    existing: Dict[str, Any],
    patch_data: Dict[str, Any],
    cotisation_id: str,
) -> Dict[str, Any]:
    merged = {**existing, **patch_data}
    if should_stamp_cotisation(cotisation_id):
        merged["last_checked_at"] = iso_now_utc()
    return merged


def new_cotisation_item(patch_data: Dict[str, Any], cotisation_id: str) -> Dict[str, Any]:
    item = {**patch_data}
    if should_stamp_cotisation(cotisation_id):
        item["last_checked_at"] = iso_now_utc()
    return item


def stamp_cotisation_inplace(item: Dict[str, Any], cotisation_id: str) -> None:
    if should_stamp_cotisation(cotisation_id):
        item["last_checked_at"] = iso_now_utc()


def strip_cotisation_check_timestamps(config_data: Dict[str, Any]) -> Dict[str, Any]:
    data = copy.deepcopy(config_data)
    for item in data.get("cotisations", []):
        if isinstance(item, dict):
            item.pop("last_checked_at", None)
    return data


def cotisations_rates_equal(
    current: Dict[str, Any],
    new: Dict[str, Any],
) -> bool:
    return strip_cotisation_check_timestamps(current) == strip_cotisation_check_timestamps(
        new
    )


def persist_cotisations_config(
    supabase: Client,
    current_row: Optional[Dict[str, Any]],
    new_config_data: Dict[str, Any],
    source_links: List[str],
    comment: str,
) -> None:
    """
    Persiste config_data cotisations avec horodatage par ligne ciblée.
    last_checked_at au niveau payroll_config uniquement si sync globale cotisations.
    """
    if current_row is None:
        logging.info(
            "Aucune config existante. Insertion de la v1 pour '%s'.",
            CONFIG_KEY_COTISATIONS,
        )
        new_row = {
            "config_key": CONFIG_KEY_COTISATIONS,
            "config_data": new_config_data,
            "version": 1,
            "is_active": True,
            "comment": comment,
            "last_checked_at": iso_now_utc(),
            "source_links": source_links,
        }
        supabase.table("payroll_config").insert(new_row).execute()
        logging.info("✅ Succès: '%s' v1 créée.", CONFIG_KEY_COTISATIONS)
        return

    current_config_data = current_row["config_data"]
    current_id = current_row["id"]
    current_version = current_row["version"]
    touch_category = is_full_cotisations_sync()

    if cotisations_rates_equal(current_config_data, new_config_data):
        logging.info(
            "Les données '%s' sont inchangées (taux). Mise à jour des contrôles ciblés.",
            comment,
        )
        payload: Dict[str, Any] = {
            "config_data": new_config_data,
            "source_links": source_links,
        }
        if touch_category:
            payload["last_checked_at"] = iso_now_utc()
        supabase.table("payroll_config").update(payload).eq("id", current_id).execute()
        logging.info("✅ Succès: contrôles cotisations mis à jour.")
        return

    logging.warning(
        "Différence détectée pour '%s'. Création de la version %s...",
        comment,
        current_version + 1,
    )
    new_row = {
        "config_key": CONFIG_KEY_COTISATIONS,
        "config_data": new_config_data,
        "version": current_version + 1,
        "is_active": True,
        "comment": comment,
        "source_links": source_links,
    }
    if touch_category:
        new_row["last_checked_at"] = iso_now_utc()

    logging.info(
        "Désactivation de la version %s (ID: %s)...",
        current_version,
        current_id,
    )
    supabase.table("payroll_config").update({"is_active": False}).eq("id", current_id).execute()
    logging.info("Insertion de la version %s...", current_version + 1)
    supabase.table("payroll_config").insert(new_row).execute()
    logging.info(
        "✅ Succès: '%s' mis à jour vers v%s.",
        CONFIG_KEY_COTISATIONS,
        current_version + 1,
    )
