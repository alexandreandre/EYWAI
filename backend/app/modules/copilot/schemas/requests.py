"""
Schémas Pydantic entrée API pour le module copilot.

Contrats alignés sur api/routers/copilot.py et api/routers/copilot_agent.py.
Migration : à remplacer par les mêmes définitions une fois le code migré.
"""

from typing import List, Optional

from pydantic import BaseModel


# --- Text-to-SQL (POST /query) ---
class QueryRequest(BaseModel):
    """Requête Text-to-SQL : prompt utilisateur."""

    prompt: str


# --- Agent (POST /query-agent) ---
class AgentMessage(BaseModel):
    """Message dans l'historique de conversation (role + contenu)."""

    role: str  # "user" | "assistant" | "system"
    content: str


class AgentRequest(BaseModel):
    """Requête agent : prompt + historique de conversation optionnel."""

    prompt: str
    conversation_history: Optional[List[AgentMessage]] = []
