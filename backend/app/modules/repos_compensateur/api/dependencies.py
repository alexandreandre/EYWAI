"""
Dépendances FastAPI du module repos_compensateur.

- ReposCompensateurUserContext : contrat minimal (active_company_id) pour éviter
  de dépendre de app.modules.users ; satisfait par le User retourné par get_current_user.
- get_current_user (app.core.security) pour les routes protégées (calculer-credits).
"""
from __future__ import annotations

from typing import Protocol

from app.core.security import get_current_user


class ReposCompensateurUserContext(Protocol):
    """Contrat minimal du contexte utilisateur pour les routes repos_compensateur."""

    active_company_id: str | None


__all__ = ["ReposCompensateurUserContext", "get_current_user"]
