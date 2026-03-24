"""
Dépendances FastAPI du module collective_agreements.

Contrat minimal du contexte utilisateur (Protocol) ; get_current_user fourni par app.core.security.
"""
from __future__ import annotations

from typing import Optional, Protocol

from app.core.security import get_current_user


class CollectiveAgreementUserContext(Protocol):
    """Contrat minimal du contexte utilisateur pour les routes collective_agreements."""

    active_company_id: Optional[str]
    id: str
    role: str

    def has_rh_access_in_company(self, company_id: str) -> bool:
        ...


__all__ = ["CollectiveAgreementUserContext", "get_current_user"]
