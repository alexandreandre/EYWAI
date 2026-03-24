"""
Ports (interfaces) pour le contrôle d'accès.

Aucune dépendance à FastAPI ni à la base : types built-in / typing uniquement.
L'infrastructure implémente ces interfaces ; l'application et le service ne dépendent
que des abstractions.
"""
from __future__ import annotations

from typing import Any, Protocol


class IPermissionRepository(Protocol):
    """Accès lecture aux permissions utilisateur (user_permissions, permissions)."""

    def user_has_permission(
        self,
        user_id: str,
        company_id: str,
        permission_code: str,
    ) -> bool:
        """Vérifie si l'utilisateur possède la permission donnée dans l'entreprise."""
        ...

    def user_has_any_rh_permission(self, user_id: str, company_id: str) -> bool:
        """Vérifie si l'utilisateur custom a au moins une permission dont required_role in ('rh','admin')."""
        ...


class IPermissionCatalogReader(Protocol):
    """Lecture du catalogue de permissions (catégories, actions, permissions) et des permissions utilisateur."""

    def get_permission_categories_active(self) -> list[dict[str, Any]]:
        """Liste des catégories actives, tri display_order."""
        ...

    def get_permission_actions_active(self) -> list[dict[str, Any]]:
        """Liste des actions actives, tri label."""
        ...

    def get_permissions_active(
        self,
        category_id: str | None = None,
        required_role: str | None = None,
    ) -> list[dict[str, Any]]:
        """Liste des permissions actives avec filtres optionnels."""
        ...

    def get_permissions_for_matrix(self) -> list[dict[str, Any]]:
        """Permissions actives pour la construction de la matrice."""
        ...

    def get_user_permission_ids(self, user_id: str, company_id: str) -> set[str]:
        """Ensemble des permission_id accordés à un utilisateur dans une entreprise."""
        ...

    def get_user_company_access(
        self, user_id: str, company_id: str
    ) -> dict[str, Any] | None:
        """Accès utilisateur à une entreprise (user_company_accesses + role_templates)."""
        ...

    def get_permissions_details_by_ids(
        self, permission_ids: list[str]
    ) -> list[dict[str, Any]]:
        """Détails des permissions (avec category et action) pour une liste d'IDs."""
        ...


class IRoleTemplateRepository(Protocol):
    """Lecture/écriture des templates de rôles et de leurs permissions."""

    def get_role_templates_list(
        self,
        company_id: str | None = None,
        base_role: str | None = None,
        include_system: bool = True,
    ) -> list[dict[str, Any]]:
        """Liste des templates (système + entreprise ou filtrés)."""
        ...

    def get_role_template_permissions_count(self, template_id: str) -> int:
        """Nombre de permissions d'un template."""
        ...

    def get_role_template_by_id(self, template_id: str) -> dict[str, Any] | None:
        """Un template par ID."""
        ...

    def get_role_template_permission_details(
        self, template_id: str
    ) -> list[dict[str, Any]]:
        """Permissions d'un template (détails)."""
        ...

    def role_template_name_exists(self, company_id: str, name: str) -> bool:
        """True si un template avec ce nom existe déjà pour l'entreprise."""
        ...

    def create_role_template(
        self,
        company_id: str,
        name: str,
        description: str | None,
        job_title: str,
        base_role: str,
        created_by: str,
    ) -> str:
        """Crée un template, retourne l'id créé."""
        ...

    def attach_permissions_to_role_template(
        self, template_id: str, permission_ids: list[str] | list[Any]
    ) -> None:
        """Associe des permissions à un template."""
        ...
