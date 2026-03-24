"""
Requêtes lecture/écriture pour le module access_control.

Accès aux tables permission_categories, permission_actions, permissions,
user_permissions, user_company_accesses, role_templates, role_template_permissions.
Retourne des structures brutes (dict, list) ; la couche application construit les DTOs/schémas.
Les classes Supabase* implémentent les ports du domain (IPermissionCatalogReader, IRoleTemplateRepository).
"""
from __future__ import annotations

from typing import Any
from uuid import UUID

from app.core.database import supabase
from app.modules.access_control.domain.interfaces import (
    IPermissionCatalogReader,
    IRoleTemplateRepository,
)


def get_permission_categories_active() -> list[dict[str, Any]]:
    """Liste les catégories de permissions actives, tri par display_order."""
    result = (
        supabase.table("permission_categories")
        .select("*")
        .eq("is_active", True)
        .order("display_order")
        .execute()
    )
    return result.data or []


def get_permission_actions_active() -> list[dict[str, Any]]:
    """Liste les actions de permissions actives, tri par label."""
    result = (
        supabase.table("permission_actions")
        .select("*")
        .eq("is_active", True)
        .order("label")
        .execute()
    )
    return result.data or []


def get_permissions_active(
    category_id: str | None = None,
    required_role: str | None = None,
) -> list[dict[str, Any]]:
    """Liste les permissions actives, avec filtres optionnels."""
    query = supabase.table("permissions").select("*").eq("is_active", True)
    if category_id:
        query = query.eq("category_id", category_id)
    if required_role:
        query = query.eq("required_role", required_role)
    result = query.order("label").execute()
    return result.data or []


def get_permissions_for_matrix() -> list[dict[str, Any]]:
    """Toutes les permissions actives avec id, code, label, description, category_id, action_id, required_role, is_active."""
    result = (
        supabase.table("permissions")
        .select("id, code, label, description, category_id, action_id, required_role, is_active")
        .eq("is_active", True)
        .execute()
    )
    return result.data or []


def get_user_permission_ids(user_id: str, company_id: str) -> set[str]:
    """Ensemble des permission_id accordés à un utilisateur dans une entreprise."""
    result = (
        supabase.table("user_permissions")
        .select("permission_id")
        .eq("user_id", str(user_id))
        .eq("company_id", str(company_id))
        .execute()
    )
    return {str(row["permission_id"]) for row in (result.data or [])}


def get_user_company_access(user_id: str, company_id: str) -> dict[str, Any] | None:
    """Accès utilisateur à une entreprise (user_company_accesses + role_templates)."""
    result = (
        supabase.table("user_company_accesses")
        .select("*, role_templates(*)")
        .eq("user_id", str(user_id))
        .eq("company_id", str(company_id))
        .execute()
    )
    if not result.data or len(result.data) == 0:
        return None
    return result.data[0]


def get_permissions_details_by_ids(
    permission_ids: list[str],
) -> list[dict[str, Any]]:
    """Détails des permissions (avec category et action) pour une liste d'IDs."""
    if not permission_ids:
        return []
    result = (
        supabase.table("permissions")
        .select("*, permission_categories(*), permission_actions(*)")
        .in_("id", permission_ids)
        .eq("is_active", True)
        .execute()
    )
    return result.data or []


def get_role_templates_list(
    company_id: str | None = None,
    base_role: str | None = None,
    include_system: bool = True,
) -> list[dict[str, Any]]:
    """
    Liste des templates de rôles. Si include_system et company_id: templates système + templates de l'entreprise.
    Sinon filtre par company_id et is_system selon les paramètres.
    """
    if include_system and company_id:
        system_result = (
            supabase.table("role_templates")
            .select("*")
            .eq("is_active", True)
            .eq("is_system", True)
            .execute()
        )
        company_result = (
            supabase.table("role_templates")
            .select("*")
            .eq("is_active", True)
            .eq("company_id", company_id)
            .execute()
        )
        templates = (system_result.data or []) + (company_result.data or [])
    else:
        query = supabase.table("role_templates").select("*").eq("is_active", True)
        if not include_system and company_id:
            query = query.eq("company_id", company_id).eq("is_system", False)
        result = query.execute()
        templates = result.data or []
    if base_role:
        templates = [t for t in templates if t.get("base_role") == base_role]
    return templates


def get_role_template_permissions_count(template_id: str) -> int:
    """Nombre de permissions d'un template."""
    result = (
        supabase.table("role_template_permissions")
        .select("id", count="exact")
        .eq("template_id", template_id)
        .execute()
    )
    return result.count or 0


def get_role_template_by_id(template_id: str) -> dict[str, Any] | None:
    """Un template par ID."""
    result = (
        supabase.table("role_templates")
        .select("*")
        .eq("id", template_id)
        .execute()
    )
    if not result.data or len(result.data) == 0:
        return None
    return result.data[0]


def get_role_template_permission_details(template_id: str) -> list[dict[str, Any]]:
    """Permissions d'un template (via role_template_permissions -> permissions)."""
    result = (
        supabase.table("role_template_permissions")
        .select("permissions(*)")
        .eq("template_id", template_id)
        .execute()
    )
    return [
        row["permissions"]
        for row in (result.data or [])
        if row.get("permissions")
    ]


def role_template_name_exists(company_id: str, name: str) -> bool:
    """True si un template avec ce nom existe déjà pour l'entreprise."""
    result = (
        supabase.table("role_templates")
        .select("id")
        .eq("company_id", company_id)
        .eq("name", name)
        .execute()
    )
    return bool(result.data and len(result.data) > 0)


def create_role_template(
    company_id: str,
    name: str,
    description: str | None,
    job_title: str,
    base_role: str,
    created_by: str,
) -> str:
    """Crée un template de rôle, retourne l'id du template créé."""
    template_data = {
        "company_id": company_id,
        "name": name,
        "description": description,
        "job_title": job_title,
        "base_role": base_role,
        "is_system": False,
        "is_active": True,
        "created_by": created_by,
    }
    result = supabase.table("role_templates").insert(template_data).execute()
    if not result.data or len(result.data) == 0:
        raise RuntimeError("Erreur lors de la création du template")
    return str(result.data[0]["id"])


def attach_permissions_to_role_template(
    template_id: str,
    permission_ids: list[UUID] | list[str],
) -> None:
    """Associe des permissions à un template."""
    for permission_id in permission_ids:
        supabase.table("role_template_permissions").insert({
            "template_id": template_id,
            "permission_id": str(permission_id),
        }).execute()


# --- Implémentations des ports domain ---


class SupabasePermissionCatalogReader:
    """Implémentation de IPermissionCatalogReader via Supabase. Délègue aux fonctions ci-dessus."""

    def get_permission_categories_active(self) -> list[dict[str, Any]]:
        return get_permission_categories_active()

    def get_permission_actions_active(self) -> list[dict[str, Any]]:
        return get_permission_actions_active()

    def get_permissions_active(
        self,
        category_id: str | None = None,
        required_role: str | None = None,
    ) -> list[dict[str, Any]]:
        return get_permissions_active(
            category_id=category_id,
            required_role=required_role,
        )

    def get_permissions_for_matrix(self) -> list[dict[str, Any]]:
        return get_permissions_for_matrix()

    def get_user_permission_ids(self, user_id: str, company_id: str) -> set[str]:
        return get_user_permission_ids(user_id, company_id)

    def get_user_company_access(
        self, user_id: str, company_id: str
    ) -> dict[str, Any] | None:
        return get_user_company_access(user_id, company_id)

    def get_permissions_details_by_ids(
        self, permission_ids: list[str]
    ) -> list[dict[str, Any]]:
        return get_permissions_details_by_ids(permission_ids)


class SupabaseRoleTemplateRepository:
    """Implémentation de IRoleTemplateRepository via Supabase. Délègue aux fonctions ci-dessus."""

    def get_role_templates_list(
        self,
        company_id: str | None = None,
        base_role: str | None = None,
        include_system: bool = True,
    ) -> list[dict[str, Any]]:
        return get_role_templates_list(
            company_id=company_id,
            base_role=base_role,
            include_system=include_system,
        )

    def get_role_template_permissions_count(self, template_id: str) -> int:
        return get_role_template_permissions_count(template_id)

    def get_role_template_by_id(self, template_id: str) -> dict[str, Any] | None:
        return get_role_template_by_id(template_id)

    def get_role_template_permission_details(
        self, template_id: str
    ) -> list[dict[str, Any]]:
        return get_role_template_permission_details(template_id)

    def role_template_name_exists(self, company_id: str, name: str) -> bool:
        return role_template_name_exists(company_id, name)

    def create_role_template(
        self,
        company_id: str,
        name: str,
        description: str | None,
        job_title: str,
        base_role: str,
        created_by: str,
    ) -> str:
        return create_role_template(
            company_id=company_id,
            name=name,
            description=description,
            job_title=job_title,
            base_role=base_role,
            created_by=created_by,
        )

    def attach_permissions_to_role_template(
        self, template_id: str, permission_ids: list[str] | list[Any]
    ) -> None:
        attach_permissions_to_role_template(template_id, permission_ids)


# Instances par défaut pour l'application (injection possible pour les tests)
permission_catalog_reader: IPermissionCatalogReader = SupabasePermissionCatalogReader()
role_template_repository: IRoleTemplateRepository = SupabaseRoleTemplateRepository()
