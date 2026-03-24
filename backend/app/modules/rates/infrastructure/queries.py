"""
Constantes et paramètres de requêtes pour payroll_config (module rates).

Centralise le nom de table et les colonnes lues pour la lecture des configs actives.
"""
from __future__ import annotations

# Table Supabase
PAYROLL_CONFIG_TABLE = "payroll_config"

# Colonnes sélectionnées (comportement identique au legacy)
PAYROLL_CONFIG_SELECT_COLUMNS = (
    "config_key",
    "config_data",
    "version",
    "last_checked_at",
    "is_active",
    "created_at",
    "comment",
    "source_links",
)
