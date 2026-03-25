"""
Schémas de requête du module users (définitions canoniques).

Migrés depuis schemas/user.py et schemas/permissions.py (partie création/mise à jour utilisateur).
Comportement identique. Compatibilité : schemas.user et schemas.permissions réexportent depuis ce module.
"""

from typing import List, Optional

from pydantic import BaseModel, Field
from uuid import UUID


# ----- Depuis schemas/user.py -----


class SetPrimaryCompanyRequest(BaseModel):
    """Requête pour changer l'entreprise primaire d'un utilisateur"""

    company_id: str

    class Config:
        json_schema_extra = {
            "example": {"company_id": "660e8400-e29b-41d4-a716-446655440001"}
        }


class UserCompanyAccessCreate(BaseModel):
    """Modèle pour créer un nouvel accès utilisateur à une entreprise"""

    user_email: str
    company_id: str
    role: str
    is_primary: bool = False

    class Config:
        json_schema_extra = {
            "example": {
                "user_email": "nouveau@example.com",
                "company_id": "660e8400-e29b-41d4-a716-446655440001",
                "role": "rh",
                "is_primary": False,
            }
        }


class UserCompanyAccessCreateByUserId(BaseModel):
    """Modèle pour accorder un accès par user_id (ex: après création employé, pas d'email dans profiles)"""

    user_id: str
    company_id: str
    role: str
    is_primary: bool = False

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "550e8400-e29b-41d4-a716-446655440000",
                "company_id": "660e8400-e29b-41d4-a716-446655440001",
                "role": "collaborateur_rh",
                "is_primary": True,
            }
        }


class UserCompanyAccessUpdate(BaseModel):
    """Modèle pour modifier un accès utilisateur"""

    role: Optional[str] = None
    is_primary: Optional[bool] = None


# ----- Depuis schemas/permissions.py (création/mise à jour utilisateur) -----


class UserCompanyAccessData(BaseModel):
    """Représente un accès à une entreprise pour un utilisateur"""

    company_id: UUID = Field(..., description="ID de l'entreprise")
    base_role: str = Field(
        ...,
        pattern="^(admin|rh|collaborateur_rh|collaborateur|custom)$",
        description="Rôle de base dans l'entreprise (admin/rh/collaborateur_rh/collaborateur pour rôles système, custom pour rôles personnalisés)",
    )
    is_primary: bool = Field(False, description="Entreprise principale")
    role_template_id: Optional[UUID] = Field(
        None, description="ID du template de rôle à appliquer"
    )
    permission_ids: List[UUID] = Field(
        default_factory=list, description="Liste des IDs de permissions additionnelles"
    )
    contract_type: Optional[str] = Field(
        None,
        description="Type de contrat (ex: CDI, CDD, Intérim, etc.) - utilisé pour les accès collaborateur",
    )
    statut: Optional[str] = Field(
        None,
        description="Statut de l'employé (ex: Non-Cadre, Cadre, Cadre au forfait jour) - détermine si l'employé travaille en forfait jour",
    )


class UserCreateWithPermissions(BaseModel):
    """Schéma pour créer un utilisateur avec ses permissions"""

    # Informations de base
    email: str = Field(..., description="Email de l'utilisateur")
    username: Optional[str] = Field(None, description="Nom d'utilisateur (optionnel)")
    password: str = Field(
        ..., min_length=8, description="Mot de passe (min 8 caractères)"
    )
    first_name: str = Field(..., max_length=100, description="Prénom")
    last_name: str = Field(..., max_length=100, description="Nom")
    phone: Optional[str] = Field(None, max_length=20, description="Téléphone")
    job_title: Optional[str] = Field(
        None, max_length=100, description="Titre du poste global"
    )

    # Accès entreprises (peut en avoir plusieurs)
    company_accesses: List[UserCompanyAccessData] = Field(
        ...,
        min_length=1,
        description="Liste des accès entreprises pour cet utilisateur",
    )


class UserUpdateWithPermissions(BaseModel):
    """Schéma pour mettre à jour un utilisateur et ses permissions"""

    # Informations modifiables
    first_name: Optional[str] = Field(None, max_length=100)
    last_name: Optional[str] = Field(None, max_length=100)
    job_title: Optional[str] = Field(None, max_length=100)

    # Modification de l'accès (optionnel)
    company_id: UUID = Field(..., description="ID de l'entreprise concernée")
    base_role: Optional[str] = Field(
        None, pattern="^(admin|rh|collaborateur_rh|collaborateur|custom)$"
    )
    role_template_id: Optional[UUID] = None
    permission_ids: Optional[List[UUID]] = Field(
        None,
        description="Liste complète des permissions (remplace toutes les existantes)",
    )


__all__ = [
    "SetPrimaryCompanyRequest",
    "UserCompanyAccessCreate",
    "UserCompanyAccessCreateByUserId",
    "UserCompanyAccessUpdate",
    "UserCompanyAccessData",
    "UserCreateWithPermissions",
    "UserUpdateWithPermissions",
]
