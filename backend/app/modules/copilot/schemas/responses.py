"""
Schémas Pydantic sortie API pour le module copilot.

Contrats alignés sur api/routers/copilot.py et api/routers/copilot_agent.py.
"""

from typing import Optional

from pydantic import BaseModel


# --- Text-to-SQL (POST /query) ---
class QueryResponse(BaseModel):
    """Réponse publique historique, sans SQL ni données brutes."""

    answer: str


# --- Agent (POST /query-agent) ---
class AgentResponse(BaseModel):
    """Réponse agent publique ; uniquement la réponse synthétisée."""

    answer: str
    needs_clarification: bool = False
    clarification_question: Optional[str] = None
