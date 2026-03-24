"""
Implémentation du port IAllRatesReader via Supabase (table payroll_config).

Ne fait que la lecture brute ; le groupement et le formatage sont en domain/application.
"""
from __future__ import annotations

import logging
from typing import Any

from app.core.database import get_supabase_admin_client

from app.modules.rates.infrastructure.queries import (
    PAYROLL_CONFIG_SELECT_COLUMNS,
    PAYROLL_CONFIG_TABLE,
)


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
