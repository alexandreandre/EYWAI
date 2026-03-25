"""
Contrat de type pour l'utilisateur courant dans le module company_groups.

Permet au router de ne pas dépendre de app.modules.users : on utilise un Protocol
décrivant uniquement les attributs utilisés (is_super_admin, accessible_companies,
is_admin_in_company). get_current_user (app.core.security) retourne à l'exécution
un User qui satisfait ce contrat.
"""

from __future__ import annotations

from typing import List, Protocol, runtime_checkable


@runtime_checkable
class AccessibleCompanyForGroups(Protocol):
    """Contrat minimal d'un accès entreprise utilisé par le router."""

    company_id: str
    role: str


@runtime_checkable
class CurrentUserForCompanyGroups(Protocol):
    """
    Contrat minimal de l'utilisateur courant pour les endpoints company_groups.
    Satisfait par app.modules.users.schemas.responses.User (retour de get_current_user).
    """

    is_super_admin: bool
    accessible_companies: List[AccessibleCompanyForGroups]

    def is_admin_in_company(self, company_id: str) -> bool: ...
