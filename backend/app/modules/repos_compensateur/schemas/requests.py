"""
Schémas Pydantic entrée API du module repos_compensateur.

Aucun body : l’endpoint calculer-credits utilise uniquement des query params (year, month, company_id). Comportement identique au legacy.
"""
from __future__ import annotations

# Pas de body pour l’instant ; query params gérés dans le router
