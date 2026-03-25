"""
Dépendances FastAPI du module bonus_types.

Définit le contrat minimal du contexte utilisateur (Protocol) pour ne pas
dépendre d'app.modules.users ; get_current_user reste fourni par app.core.security.
"""

from __future__ import annotations

from typing import Optional, Protocol

from app.core.security import get_current_user


class BonusTypeUserContext(Protocol):
    """Contrat minimal du contexte utilisateur pour les routes bonus_types.
    Satisfait par app.modules.users.schemas.responses.User (duck typing).
    """

    active_company_id: Optional[str]
    id: str
    is_super_admin: bool

    def has_rh_access_in_company(self, company_id: str) -> bool: ...


__all__ = ["BonusTypeUserContext", "get_current_user"]
