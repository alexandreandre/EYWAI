"""
Commandes du module super_admin (couche application).

Applique les règles métier (domain) puis délègue à l'infrastructure (DB).
Comportement identique.
"""

from __future__ import annotations

from typing import Any, Dict

from app.modules.super_admin.domain.exceptions import SuperAdminPermissionDenied
from app.modules.super_admin.domain import rules as domain_rules
from app.modules.super_admin.infrastructure import commands as infra_commands
from app.modules.super_admin.infrastructure.mappers import row_to_super_admin

from app.modules.super_admin.application.service import SuperAdminAccessError


def create_company_with_admin(
    company_data: Dict[str, Any],
    super_admin_row: Dict[str, Any],
) -> Dict[str, Any]:
    """Crée une entreprise et optionnellement un admin. Vérifie can_create_companies."""
    try:
        super_admin = row_to_super_admin(super_admin_row)
        domain_rules.require_can_create_companies(super_admin)
    except SuperAdminPermissionDenied as e:
        raise SuperAdminAccessError(str(e)) from e
    return infra_commands.create_company_with_admin(company_data, super_admin_row)


def update_company(company_id: str, update_data: Dict[str, Any]) -> Dict[str, Any]:
    """Met à jour une entreprise."""
    return infra_commands.update_company(company_id, update_data)


def delete_company_soft(
    company_id: str, super_admin_row: Dict[str, Any]
) -> Dict[str, Any]:
    """Désactive une entreprise (is_active=False). Vérifie can_delete_companies."""
    try:
        super_admin = row_to_super_admin(super_admin_row)
        domain_rules.require_can_delete_companies(super_admin)
    except SuperAdminPermissionDenied as e:
        raise SuperAdminAccessError(str(e)) from e
    return infra_commands.delete_company_soft(company_id)


def delete_company_permanent(
    company_id: str, super_admin_row: Dict[str, Any]
) -> Dict[str, Any]:
    """Supprime définitivement une entreprise. Vérifie can_delete_companies."""
    try:
        super_admin = row_to_super_admin(super_admin_row)
        domain_rules.require_can_delete_companies(super_admin)
    except SuperAdminPermissionDenied as e:
        raise SuperAdminAccessError(str(e)) from e
    return infra_commands.delete_company_permanent(company_id)


def create_company_user(company_id: str, user_data: Dict[str, Any]) -> Dict[str, Any]:
    """Crée un utilisateur pour une entreprise (Auth + profile + user_company_accesses)."""
    return infra_commands.create_company_user(company_id, user_data)


def update_company_user(
    company_id: str,
    user_id: str,
    update_data: Dict[str, Any],
) -> Dict[str, Any]:
    """Met à jour un utilisateur (profil, rôle, email)."""
    return infra_commands.update_company_user(company_id, user_id, update_data)


def delete_company_user(company_id: str, user_id: str) -> Dict[str, Any]:
    """Retire l'accès utilisateur à l'entreprise ; supprime user si plus aucun accès."""
    return infra_commands.delete_company_user(company_id, user_id)
