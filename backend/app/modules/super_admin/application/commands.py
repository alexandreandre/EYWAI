"""
Commandes du module super_admin (couche application).

Applique les règles métier (domain) puis délègue à l'infrastructure (DB).
Comportement identique.
"""

from __future__ import annotations

from typing import Any, Dict, Iterator, Optional, Tuple

from app.modules.super_admin.domain.exceptions import SuperAdminPermissionDenied
from app.modules.super_admin.domain import rules as domain_rules
from app.modules.super_admin.infrastructure import commands as infra_commands
from app.modules.super_admin.infrastructure.mappers import row_to_super_admin

from app.modules.super_admin.application.service import SuperAdminAccessError
from app.modules.audit.infrastructure.repository import audit_repository


def _actor_from_super_admin_row(super_admin_row: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    uid = super_admin_row.get("user_id") or super_admin_row.get("id")
    return (str(uid) if uid else None, super_admin_row.get("email"))


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
    result = infra_commands.create_company_with_admin(company_data, super_admin_row)
    company = result.get("company") or {}
    cid = company.get("id")
    if cid:
        actor_id, actor_email = _actor_from_super_admin_row(super_admin_row)
        audit_repository.log(
            str(cid),
            actor_id,
            actor_email,
            "company.create",
            "company",
            str(cid),
            {"company_name": company.get("company_name")},
        )
    return result


def update_company(
    company_id: str,
    update_data: Dict[str, Any],
    super_admin_row: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Met à jour une entreprise."""
    result = infra_commands.update_company(company_id, update_data)
    if super_admin_row:
        actor_id, actor_email = _actor_from_super_admin_row(super_admin_row)
        audit_repository.log(
            company_id,
            actor_id,
            actor_email,
            "company.update",
            "company",
            company_id,
            {"fields": list(update_data.keys())},
        )
    return result


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


def create_company_user(
    company_id: str,
    user_data: Dict[str, Any],
    super_admin_row: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Crée un utilisateur pour une entreprise (Auth + profile + user_company_accesses)."""
    result = infra_commands.create_company_user(company_id, user_data)
    user = result.get("user") or {}
    actor_id, actor_email = (
        _actor_from_super_admin_row(super_admin_row) if super_admin_row else (None, None)
    )
    audit_repository.log(
        company_id,
        actor_id,
        actor_email,
        "user.create",
        "user",
        str(user.get("id") or ""),
        {"email": user_data.get("email"), "role": user_data.get("role")},
    )
    return result


def update_company_user(
    company_id: str,
    user_id: str,
    update_data: Dict[str, Any],
    super_admin_row: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Met à jour un utilisateur (profil, rôle, email)."""
    result = infra_commands.update_company_user(company_id, user_id, update_data)
    action = "user.role_change" if "role" in update_data else "user.update"
    if super_admin_row:
        actor_id, actor_email = _actor_from_super_admin_row(super_admin_row)
        audit_repository.log(
            company_id,
            actor_id,
            actor_email,
            action,
            "user",
            user_id,
            {"fields": list(update_data.keys())},
        )
    return result


def delete_company_user(company_id: str, user_id: str) -> Dict[str, Any]:
    """Retire l'accès utilisateur à l'entreprise ; supprime user si plus aucun accès."""
    return infra_commands.delete_company_user(company_id, user_id)


def delete_all_company_employees(
    company_id: str, super_admin_row: Dict[str, Any]
) -> Dict[str, Any]:
    """Supprime tous les employés d'une entreprise (admin plateforme actif)."""
    result: Dict[str, Any] | None = None
    for event in iter_delete_all_company_employees_stream(company_id, super_admin_row):
        if event.get("event") == "completed":
            result = event.get("result")
    if result is None:
        raise RuntimeError("Suppression interrompue sans résultat final")
    return result


def iter_delete_all_company_employees_stream(
    company_id: str, super_admin_row: Dict[str, Any]
) -> Iterator[Dict[str, Any]]:
    """Flux NDJSON de suppression de tous les employés + audit en fin de parcours."""
    from app.modules.employees.application.commands import (
        iter_delete_all_company_employees,
    )

    final_result: Dict[str, Any] | None = None
    try:
        for event in iter_delete_all_company_employees(company_id):
            if event.get("event") == "completed":
                final_result = event.get("result")
            yield event
    except LookupError:
        yield {"event": "error", "message": "Entreprise non trouvée"}
        return

    if final_result is not None:
        actor_id, actor_email = _actor_from_super_admin_row(super_admin_row)
        audit_repository.log(
            company_id,
            actor_id,
            actor_email,
            "company.delete_all_employees",
            "company",
            company_id,
            {
                "requested_count": final_result.get("requested_count", 0),
                "removed_count": final_result.get("removed_count", 0),
                "failed_count": len(final_result.get("failed") or []),
            },
        )
