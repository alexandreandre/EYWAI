"""
Dépendances FastAPI du module participation.

Contrat minimal du contexte utilisateur (Protocol) pour ne pas dépendre
d'app.modules.users ; get_current_user reste fourni par app.core.security.
Satisfait par duck typing avec le type User retourné par get_current_user.
"""

from __future__ import annotations

from typing import Optional, Protocol

from app.core.security import get_current_user


class ParticipationUserContext(Protocol):
    """Contrat minimal du contexte utilisateur pour les routes participation.
    Utilisé pour id et active_company_id uniquement.
    """

    id: str
    active_company_id: Optional[str]


__all__ = ["ParticipationUserContext", "get_current_user"]
