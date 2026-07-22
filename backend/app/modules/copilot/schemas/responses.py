"""
Schémas Pydantic sortie API pour le module copilot.
"""

from typing import Optional

from pydantic import BaseModel


# --- Endpoint historique désactivé (POST /query) ---
class QueryResponse(BaseModel):
    """Réponse minimale conservée pour la compatibilité de route."""

    answer: str


# --- Agent (POST /query-agent) ---
class AgentResponse(BaseModel):
    """Réponse agent publique ; uniquement la réponse synthétisée."""

    answer: str
    needs_clarification: bool = False
    clarification_question: Optional[str] = None
