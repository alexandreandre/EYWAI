"""
Service applicatif users : orchestration et délégation.

Délègue au domain (règles pures) et à l'infrastructure (repositories, providers).
Plus d'accès DB direct ici.
"""

from typing import Any

from app.modules.users.domain import rules as domain_rules
from app.modules.users.infrastructure.providers import (
    auth_provider,
    credentials_pdf_provider,
    storage_provider,
)
from app.modules.users.infrastructure.repository import (
    company_repository,
    role_template_repository,
    user_company_access_repository,
    user_permission_repository,
    user_repository,
)


# --- Accès clients (compatibilité : appelants externes ou tests) ---
def get_supabase():
    """Client Supabase par défaut (délégation app.core.database)."""
    from app.core.database import supabase

    return supabase


def get_admin_client():
    """Client Supabase admin (délégation app.core.database)."""
    from app.core.database import get_supabase_admin_client

    return get_supabase_admin_client()


# --- Règles métier (domain) ---
def check_role_hierarchy(creator_user: Any, target_role: str, company_id: str) -> bool:
    return domain_rules.check_role_hierarchy(creator_user, target_role, company_id)


# --- Permissions (infrastructure) ---
def has_any_rh_permission(user_id: str, company_id: str) -> bool:
    return user_permission_repository.has_any_rh_permission(user_id, company_id)


def copy_template_permissions_to_user(
    template_id: str, user_id: str, company_id: str, granted_by: str
) -> None:
    user_permission_repository.copy_from_template(
        template_id, user_id, company_id, granted_by
    )


def get_default_system_template_id(base_role: str):
    return role_template_repository.get_default_system_template_id(base_role)


def get_credentials_logo_path():
    from pathlib import Path

    return Path(credentials_pdf_provider.get_logo_path())


# --- Repositories / providers exposés pour commands et queries ---
def get_user_repository():
    return user_repository


def get_user_company_access_repository():
    return user_company_access_repository


def get_company_repository():
    return company_repository


def get_role_template_repository():
    return role_template_repository


def get_user_permission_repository():
    return user_permission_repository


def get_auth_provider():
    return auth_provider


def get_credentials_pdf_provider():
    return credentials_pdf_provider


def get_storage_provider():
    return storage_provider
