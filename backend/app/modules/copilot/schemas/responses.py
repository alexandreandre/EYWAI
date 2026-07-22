"""
Schémas Pydantic sortie API pour le module copilot.

Contrats alignés sur api/routers/copilot.py et api/routers/copilot_agent.py.
"""

from typing import Any, List, Optional

from pydantic import BaseModel


# --- Text-to-SQL (POST /query) ---
class QueryResponse(BaseModel):
    """Réponse Text-to-SQL publique ; SQL et données restent neutralisés."""

    answer: str
    sql_query: str
    data: Optional[Any] = None


# --- Agent (POST /query-agent) ---
class AgentResponse(BaseModel):
    """Réponse agent publique ; détails internes et données restent neutralisés."""

    answer: str
    needs_clarification: bool = False
    clarification_question: Optional[str] = None
    sql_queries: Optional[List[str]] = None
    data: Optional[Any] = None
    thought_process: Optional[str] = None
