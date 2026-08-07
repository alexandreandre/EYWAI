"""
DTOs applicatifs pour le module copilot.

Objets de transfert entre api et application (entrée/sortie des cas d'usage).
Sans dépendance FastAPI.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class TextToSqlInput:
    """Entrée de l'ancien endpoint /query, conservé uniquement pour répondre 503."""

    prompt: str
    user_id: str
    active_company_id: Optional[str] = None


@dataclass
class TextToSqlResult:
    """Réponse minimale de compatibilité de l'ancien endpoint désactivé."""

    answer: str


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
    active_company_id: Optional[str] = None
    # Rôle de l'utilisateur DANS l'entreprise active. Il décide du périmètre des
    # outils nominatifs : un rôle nommé (admin/rh) couvre l'entreprise, un rôle
    # `custom` ne voit que ce que ses grants autorisent.
    user_role: str = ""


@dataclass
class AgentQueryResult:
    """Résultat applicatif public, limité à la réponse synthétisée."""

    answer: str
    needs_clarification: bool = False
    clarification_question: Optional[str] = None
