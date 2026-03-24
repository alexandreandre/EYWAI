"""
Enums du domaine copilot.
"""
from enum import Enum


class MessageRole(str, Enum):
    """Rôle d'un message dans la conversation (aligné sur OpenAI)."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
