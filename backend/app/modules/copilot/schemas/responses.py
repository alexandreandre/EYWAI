"""
Schémas Pydantic sortie API pour le module copilot.

Contrats alignés sur api/routers/copilot.py et api/routers/copilot_agent.py.
"""
from typing import Any, List, Optional

from pydantic import BaseModel


# --- Text-to-SQL (POST /query) ---
class QueryResponse(BaseModel):
    """Réponse Text-to-SQL : réponse formatée, SQL exécuté, données brutes."""

    answer: str
    sql_query: str
    data: Optional[Any] = None


# --- Agent (POST /query-agent) ---
class AgentResponse(BaseModel):
    """Réponse agent : réponse, clarification éventuelle, SQL et données pour debug."""

    answer: str
    needs_clarification: bool = False
    clarification_question: Optional[str] = None
    sql_queries: Optional[List[str]] = None
    data: Optional[Any] = None
    thought_process: Optional[str] = None
