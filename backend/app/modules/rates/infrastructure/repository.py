"""
Implémentation du port IAllRatesReader via Supabase (table payroll_config).

Ne fait que la lecture brute ; le groupement et le formatage sont en domain/application.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from app.core.database import get_supabase_admin_client

from app.modules.rates.infrastructure.queries import (
    PAYROLL_CONFIG_SELECT_COLUMNS,
    PAYROLL_CONFIG_TABLE,
)


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SupabaseAllRatesReader:
    """Lecture des lignes actives de payroll_config (sans logique de groupement)."""

    def get_all_active_rows(self) -> list[dict[str, Any]]:
        """Retourne toutes les lignes actives (is_active=True)."""
        supabase = get_supabase_admin_client()
        logging.info("🔍 Lecture de la table payroll_config (is_active = true)...")
        columns = ", ".join(PAYROLL_CONFIG_SELECT_COLUMNS)
        response = (
            supabase.table(PAYROLL_CONFIG_TABLE)
            .select(columns)
            .eq("is_active", True)
            .execute()
        )
        return list(response.data) if response.data else []


class SupabaseRatesWriter:
    """
    Écriture manuelle versionnée de payroll_config.

    Réplique fidèlement la stratégie de versioning immuable utilisée par le
    pipeline de scraping (`persist_full_config`) mais scopée à la couche
    infrastructure du module rates, afin de ne pas importer le package scraping
    depuis l'application (frontière de module + bootstrap sys.path/env distinct).
    """

    def get_active_config(self, config_key: str) -> dict[str, Any] | None:
        supabase = get_supabase_admin_client()
        response = (
            supabase.table(PAYROLL_CONFIG_TABLE)
            .select("*")
            .eq("config_key", config_key)
            .eq("is_active", True)
            .maybe_single()
            .execute()
        )
        if response is None:
            return None
        return response.data

    def save_manual_version(
        self,
        *,
        config_key: str,
        new_config_data: dict[str, Any],
        comment: str,
        source_links: list[str],
    ) -> dict[str, Any]:
        supabase = get_supabase_admin_client()
        current_row = self.get_active_config(config_key)

        # Première version : aucune config active existante.
        if current_row is None:
            row = {
                "config_key": config_key,
                "config_data": new_config_data,
                "version": 1,
                "is_active": True,
                "comment": comment,
                "last_checked_at": _iso_now(),
                "source_links": source_links,
            }
            inserted = supabase.table(PAYROLL_CONFIG_TABLE).insert(row).execute()
            new_id = inserted.data[0]["id"] if inserted and inserted.data else None
            logging.info("Config %s créée manuellement (v1)", config_key)
            return {
                "config_key": config_key,
                "version": 1,
                "changed": True,
                "id": new_id,
            }

        current_id = current_row["id"]
        current_version = int(current_row.get("version") or 1)

        # Aucun changement réel : on horodate seulement le contrôle manuel.
        if current_row.get("config_data") == new_config_data:
            supabase.table(PAYROLL_CONFIG_TABLE).update(
                {"last_checked_at": _iso_now(), "source_links": source_links}
            ).eq("id", current_id).execute()
            logging.info("Config %s inchangée (saisie manuelle)", config_key)
            return {
                "config_key": config_key,
                "version": current_version,
                "changed": False,
                "id": current_id,
            }

        new_row = {
            "config_key": config_key,
            "config_data": new_config_data,
            "version": current_version + 1,
            "is_active": True,
            "comment": comment,
            "last_checked_at": _iso_now(),
            "source_links": source_links,
        }
        try:
            supabase.table(PAYROLL_CONFIG_TABLE).update({"is_active": False}).eq(
                "id", current_id
            ).execute()
            inserted = supabase.table(PAYROLL_CONFIG_TABLE).insert(new_row).execute()
            new_id = inserted.data[0]["id"] if inserted and inserted.data else None
            logging.info(
                "Config %s saisie manuellement → v%s", config_key, current_version + 1
            )
        except Exception:
            # Rollback : réactiver la version précédente pour ne jamais laisser
            # le moteur de paie sans ligne active.
            logging.warning("Rollback saisie manuelle %s : réactivation v%s", config_key, current_version)
            supabase.table(PAYROLL_CONFIG_TABLE).update({"is_active": True}).eq(
                "id", current_id
            ).execute()
            raise

        return {
            "config_key": config_key,
            "version": current_version + 1,
            "changed": True,
            "id": new_id,
        }
