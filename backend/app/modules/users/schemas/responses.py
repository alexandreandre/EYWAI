"""
Schémas de réponse du module users (définitions canoniques).

Migrés depuis schemas/user.py — comportement identique.
Compatibilité : schemas.user réexporte depuis ce module.
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, computed_field


class CompanyAccess(BaseModel):
    """Représente l'accès d'un utilisateur à une entreprise"""

    company_id: str
    company_name: str
    role: str  # admin, rh, collaborateur, collaborateur_rh
    is_primary: bool
    siret: Optional[str] = None
    logo_url: Optional[str] = None
    logo_scale: Optional[float] = 1.0
    group_id: Optional[str] = None
    group_name: Optional[str] = None
    group_logo_url: Optional[str] = None
    group_logo_scale: Optional[float] = 1.0

    class Config:
        json_schema_extra = {
            "example": {
                "company_id": "550e8400-e29b-41d4-a716-446655440000",
                "company_name": "Ma Société SARL",
                "role": "admin",
                "is_primary": True,
                "siret": "12345678901234",
                "logo_url": None,
                "logo_scale": 1.0,
                "group_id": None,
                "group_name": None,
                "group_logo_url": None,
                "group_logo_scale": 1.0,
            }
        }


class User(BaseModel):
    """
    Modèle utilisateur étendu pour le système multi-entreprises.

    Un utilisateur peut avoir accès à plusieurs entreprises avec des rôles différents.
    L'entreprise active (active_company_id) détermine le contexte de travail actuel.
    """

    id: str
    email: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    is_super_admin: bool = False
    is_group_admin: bool = False

    # Multi-entreprises
    accessible_companies: List[CompanyAccess] = []
    active_company_id: Optional[str] = None

    @computed_field
    @property
    def role(self) -> str:
        """
        Retourne le rôle de l'utilisateur pour l'entreprise active.
        Permet la compatibilité avec l'ancien code qui utilise user.role.
        """
        if self.is_super_admin:
            return "super_admin"

        if not self.active_company_id:
            # Si pas d'entreprise active, retourner le rôle de l'entreprise primaire
            for access in self.accessible_companies:
                if access.is_primary:
                    return access.role
            # Si aucune entreprise primaire, retourner le premier rôle
            if self.accessible_companies:
                return self.accessible_companies[0].role
            return "collaborateur"  # Fallback

        # Retourner le rôle pour l'entreprise active
        for access in self.accessible_companies:
            if access.company_id == self.active_company_id:
                return access.role

        return "collaborateur"  # Fallback

    @computed_field
    @property
    def company_id(self) -> Optional[str]:
        """
        Retourne l'ID de l'entreprise active.
        Propriété pour compatibilité avec l'ancien code.
        """
        return self.active_company_id

    def has_access_to_company(self, company_id: str) -> bool:
        """Vérifie si l'utilisateur a accès à une entreprise"""
        if self.is_super_admin:
            return True
        return any(
            access.company_id == company_id for access in self.accessible_companies
        )

    def get_role_in_company(self, company_id: str) -> Optional[str]:
        """Retourne le rôle de l'utilisateur dans une entreprise spécifique"""
        if self.is_super_admin:
            return "super_admin"

        for access in self.accessible_companies:
            if access.company_id == company_id:
                return access.role
        return None

    def is_admin_in_company(self, company_id: str) -> bool:
        """Vérifie si l'utilisateur est admin dans une entreprise"""
        if self.is_super_admin:
            return True
        return self.get_role_in_company(company_id) == "admin"

    def is_rh_in_company(self, company_id: str) -> bool:
        """Vérifie si l'utilisateur est RH dans une entreprise"""
        role = self.get_role_in_company(company_id)
        return role == "rh"

    def is_collaborateur_rh_in_company(self, company_id: str) -> bool:
        """Vérifie si l'utilisateur est collaborateur_rh dans une entreprise"""
        return self.get_role_in_company(company_id) == "collaborateur_rh"

    def has_rh_access_in_company(self, company_id: str) -> bool:
        """
        Vérifie si l'utilisateur a accès RH dans une entreprise.
        Inclut: admin, rh, collaborateur_rh, et custom avec permissions RH.
        """
        if self.is_super_admin:
            return True
        role = self.get_role_in_company(company_id)
        if role in ("admin", "rh", "collaborateur_rh"):
            return True
        # Pour les rôles custom, vérifier s'ils ont au moins une permission RH
        if role == "custom":
            # Note: Cette vérification nécessite une requête à la base de données
            # Elle sera implémentée dans user_management.py avec has_any_rh_permission()
            # Pour l'instant, on retourne False et la vérification sera faite côté router
            return False
        return False

    class Config:
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "email": "user@example.com",
                "first_name": "Jean",
                "last_name": "Dupont",
                "is_super_admin": False,
                "is_group_admin": False,
                "accessible_companies": [
                    {
                        "company_id": "660e8400-e29b-41d4-a716-446655440001",
                        "company_name": "Société A",
                        "role": "admin",
                        "is_primary": True,
                    },
                    {
                        "company_id": "660e8400-e29b-41d4-a716-446655440002",
                        "company_name": "Société B",
                        "role": "rh",
                        "is_primary": False,
                    },
                ],
                "active_company_id": "660e8400-e29b-41d4-a716-446655440001",
            }
        }


class UserSimple(BaseModel):
    """Modèle simplifié pour compatibilité avec l'ancien code"""

    id: str
    email: Optional[str] = None
    role: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    is_super_admin: bool = False


class UserDetail(BaseModel):
    """Modèle détaillé pour affichage d'un utilisateur"""

    id: str
    email: str
    first_name: str
    last_name: str
    job_title: Optional[str] = None
    company_id: str
    role: str
    role_template_name: Optional[str] = (
        None  # Nom du template de rôle pour les rôles custom
    )
    created_at: Optional[datetime] = None
    can_edit: bool = (
        False  # Indique si l'utilisateur courant peut modifier cet utilisateur
    )

    class Config:
        from_attributes = True


__all__ = [
    "CompanyAccess",
    "User",
    "UserDetail",
    "UserSimple",
]
