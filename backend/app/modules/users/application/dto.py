"""
DTOs applicatifs du module users.

Objets de transfert internes pour les cas d'usage (sans dépendance directe aux schémas HTTP).
Comportement aligné sur les réponses des anciens routers.
"""

from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class CompanyAccessDto:
    """Accès utilisateur à une entreprise (interne)."""

    company_id: str
    company_name: str
    role: str
    is_primary: bool
    siret: Optional[str] = None
    logo_url: Optional[str] = None
    logo_scale: Optional[float] = 1.0
    group_id: Optional[str] = None
    group_name: Optional[str] = None
    group_logo_url: Optional[str] = None
    group_logo_scale: Optional[float] = 1.0


@dataclass
class UserDetailDto:
    """Détail utilisateur pour liste (get_company_users)."""

    id: str
    email: str
    first_name: str
    last_name: str
    job_title: Optional[str]
    company_id: str
    role: str
    role_template_name: Optional[str]
    created_at: Optional[Any]
    can_edit: bool


@dataclass
class AccessibleCompanyDto:
    """Entreprise dans laquelle l'utilisateur peut créer des utilisateurs."""

    company_id: str
    company_name: str
    creator_role: str
    can_create_roles: list


@dataclass
class UserDetailFullDto:
    """Détail complet utilisateur pour une entreprise (get_user_detail)."""

    id: str
    email: str
    first_name: str
    last_name: str
    job_title: Optional[str]
    company_id: str
    role: str
    role_template_id: Optional[str]
    role_template_name: Optional[str]
    permission_ids: list
    can_edit: bool


@dataclass
class SetPrimaryCompanyResult:
    """Résultat de set_primary_company."""

    message: str
    company_id: str


@dataclass
class GrantAccessResult:
    """Résultat de grant_access / grant_access_by_user_id."""

    message: str
    access: Optional[dict]


@dataclass
class RevokeAccessResult:
    """Résultat de revoke_access."""

    message: str
    user_id: str
    company_id: str


@dataclass
class UpdateAccessResult:
    """Résultat de update_access."""

    message: str
    access: dict


@dataclass
class CreateUserResult:
    """Résultat de create_user_with_permissions."""

    message: str
    user_id: str
    email: str
    companies_count: int


@dataclass
class UpdateUserResult:
    """Résultat de update_user_with_permissions."""

    message: str
    user_id: str
