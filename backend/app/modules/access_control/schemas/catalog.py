"""
Schémas catalogue du module access_control (contrat API : catégories, actions, permissions, templates).

Définitions canoniques pour les endpoints du module. Contrat identique au legacy schemas.permissions.
Utilisés par api/router.py et application/queries.py. Pas d'import legacy.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field
from uuid import UUID


# =====================================================
# CATÉGORIES DE PERMISSIONS
# =====================================================


class PermissionCategoryBase(BaseModel):
    code: str = Field(..., max_length=50, description="Code unique de la catégorie")
    label: str = Field(..., max_length=100, description="Libellé de la catégorie")
    description: Optional[str] = Field(None, description="Description de la catégorie")
    display_order: int = Field(0, description="Ordre d'affichage")
    is_active: bool = Field(True, description="Catégorie active")


class PermissionCategory(PermissionCategoryBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# =====================================================
# ACTIONS DE PERMISSIONS
# =====================================================


class PermissionActionBase(BaseModel):
    code: str = Field(..., max_length=50, description="Code unique de l'action")
    label: str = Field(..., max_length=100, description="Libellé de l'action")
    description: Optional[str] = Field(None, description="Description de l'action")
    is_active: bool = Field(True, description="Action active")


class PermissionAction(PermissionActionBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# =====================================================
# PERMISSIONS
# =====================================================


class PermissionBase(BaseModel):
    category_id: UUID = Field(..., description="ID de la catégorie")
    action_id: UUID = Field(..., description="ID de l'action")
    code: str = Field(
        ..., max_length=100, description="Code unique (ex: payslips.create)"
    )
    label: str = Field(..., max_length=200, description="Libellé de la permission")
    description: Optional[str] = Field(None, description="Description")
    required_role: Optional[str] = Field(
        None,
        pattern="^(admin|rh|collaborateur_rh|collaborateur|custom)$",
        description="Rôle minimum requis",
    )
    is_active: bool = Field(True, description="Permission active")


class Permission(PermissionBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PermissionWithMetadata(BaseModel):
    """Permission avec métadonnées pour l'interface"""

    id: UUID
    code: str
    label: str
    description: Optional[str]
    category_code: str
    category_label: str
    action_code: str
    action_label: str
    required_role: Optional[str]
    is_active: bool
    is_granted: bool = Field(
        False, description="Si la permission est accordée à l'utilisateur"
    )


# =====================================================
# MATRICE ET RÉSUMÉ
# =====================================================


class PermissionMatrixCategory(BaseModel):
    """Une catégorie avec ses permissions dans la matrice"""

    code: str
    label: str
    description: Optional[str] = None
    actions: List[dict] = Field(
        default_factory=list, description="Liste des permissions/actions"
    )


class PermissionMatrix(BaseModel):
    """Structure organisée pour l'affichage des permissions"""

    categories: List[PermissionMatrixCategory] = Field(
        default_factory=list, description="Liste des catégories avec leurs actions"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "categories": [
                    {
                        "code": "payslips",
                        "label": "Bulletins de paie",
                        "description": "Gestion des bulletins de paie",
                        "actions": [
                            {
                                "code": "create",
                                "label": "Créer",
                                "permission_id": "uuid",
                                "is_granted": False,
                            }
                        ],
                    }
                ]
            }
        }


class UserPermissionsSummary(BaseModel):
    """Résumé des permissions d'un utilisateur"""

    user_id: UUID
    company_id: UUID
    base_role: str
    role_template_id: Optional[UUID]
    role_template_name: Optional[str]
    total_permissions: int
    permissions_by_category: dict = Field(
        default_factory=dict, description="Nombre de permissions par catégorie"
    )
    all_permissions: List[PermissionWithMetadata] = Field(default_factory=list)


# =====================================================
# TEMPLATES DE RÔLES
# =====================================================


class RoleTemplateBase(BaseModel):
    name: str = Field(..., max_length=100, description="Nom du template")
    description: Optional[str] = Field(None, description="Description du template")
    job_title: Optional[str] = Field(None, max_length=100, description="Titre du poste")
    base_role: str = Field(
        ...,
        pattern="^(admin|rh|collaborateur_rh|collaborateur|custom)$",
        description="Rôle de base",
    )
    company_id: Optional[UUID] = Field(
        None, description="ID de l'entreprise (NULL = template système)"
    )


class RoleTemplate(RoleTemplateBase):
    id: UUID
    is_system: bool
    is_active: bool
    created_by: Optional[UUID]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class RoleTemplateWithPermissions(RoleTemplate):
    """Template avec liste des permissions"""

    permissions: List[Permission] = Field(default_factory=list)
    permissions_count: int = Field(0, description="Nombre de permissions")


class RoleTemplateDetail(BaseModel):
    """Template avec toutes les métadonnées pour l'affichage"""

    id: UUID
    name: str
    description: Optional[str]
    job_title: Optional[str]
    base_role: str
    is_system: bool
    is_active: bool
    company_id: Optional[UUID]
    company_name: Optional[str]
    created_by: Optional[UUID]
    created_by_name: Optional[str]
    created_at: datetime
    updated_at: datetime
    permissions_count: int
    permissions: List[PermissionWithMetadata] = Field(default_factory=list)


class RoleTemplateQuickCreate(BaseModel):
    """Schéma pour créer rapidement un template avec un nom et un rôle de base"""

    name: str = Field(
        ..., max_length=100, description="Nom du template (ex: Responsable Paie)"
    )
    job_title: str = Field(..., max_length=100, description="Titre du poste")
    base_role: str = Field(
        ...,
        pattern="^(admin|rh|collaborateur_rh|collaborateur|custom)$",
        description="Rôle de base",
    )
    company_id: UUID = Field(..., description="ID de l'entreprise")
    description: Optional[str] = Field(None, description="Description du template")
    permission_ids: List[UUID] = Field(
        default_factory=list, description="Liste des IDs de permissions à associer"
    )
