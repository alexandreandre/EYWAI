# app/modules/medical_follow_up/infrastructure/database.py
"""
Accès au client Supabase pour le module suivi médical.

Utilise uniquement app.core.database (nouvelle architecture).
Aucune dépendance legacy (core.config, etc.).
"""

from app.core.database import supabase


def get_supabase():
    """Retourne le client Supabase (app.core.database)."""
    return supabase
