"""
Constantes et helpers pour les requêtes Supabase (bonus_types).

Centralise les noms de tables et colonnes ; le repository et les providers
s'y réfèrent pour garder un seul point de définition.
"""
from __future__ import annotations

# Tables
TABLE_COMPANY_BONUS_TYPES = "company_bonus_types"
TABLE_EMPLOYEE_SCHEDULES = "employee_schedules"

# Colonnes / champs utilisés par les requêtes (documentation)
# company_bonus_types: id, company_id, libelle, type, montant, seuil_heures,
#   soumise_a_cotisations, soumise_a_impot, prompt_ia, created_at, updated_at, created_by
# employee_schedules: employee_id, year, month, actual_hours (JSON avec calendrier_reel)
