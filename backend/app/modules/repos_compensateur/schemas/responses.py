"""
Schémas Pydantic sortie API du module repos_compensateur.

Migré depuis api/routers/repos_compensateur.py — comportement identique.
"""

from __future__ import annotations

from pydantic import BaseModel


class CalculerCreditsResponse(BaseModel):
    """Réponse POST /api/repos-compensateur/calculer-credits."""

    company_id: str
    year: int
    month: int
    employees_processed: int
    credits_created: int
