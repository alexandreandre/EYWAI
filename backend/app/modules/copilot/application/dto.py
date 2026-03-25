"""
DTOs applicatifs pour le module copilot.

Objets de transfert entre api et application (entrée/sortie des cas d'usage).
Sans dépendance FastAPI.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Optional


@dataclass
class TextToSqlInput:
    """Entrée du cas d'usage Text-to-SQL."""

    prompt: str
    user_id: str


@dataclass
class TextToSqlResult:
    """Résultat du cas d'usage Text-to-SQL."""

    answer: str
    sql_query: str
    data: Optional[Any] = None


@dataclass
class AgentMessageDto:
    """Message de conversation (format applicatif)."""

    role: str
    content: str


@dataclass
class AgentQueryInput:
    """Entrée du cas d'usage Agent."""

    prompt: str
    conversation_history: List[AgentMessageDto]
    user_id: str


@dataclass
class AgentQueryResult:
    """Résultat du cas d'usage Agent."""

    answer: str
    needs_clarification: bool = False
    clarification_question: Optional[str] = None
    sql_queries: Optional[List[str]] = None
    data: Optional[Any] = None
    thought_process: Optional[str] = None
