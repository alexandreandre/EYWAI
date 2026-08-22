"""
Services externes du module activation : lecture salarié/société, comptes
auth (API admin) et câblage du compte au salarié.

Le câblage reproduit EXACTEMENT celui d'un compte salarié créé par
create_employee (employees) : profil `profiles`, accès société
user_company_accesses (template collaborateur) et lien employees.user_id —
c'est la première branche de resolve_employee_id_for_user_account.
À la différence de la création : un profil ou un accès DÉJÀ existant n'est
jamais écrasé (on ne rétrograde pas un compte RH qui serait aussi salarié).
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from app.core.database import supabase
from app.core.logging import get_logger

logger = get_logger("modules.activation.providers")


# ----- Lecture salarié / société -----


def get_employee_for_activation(employee_id: str) -> Optional[Dict[str, Any]]:
    response = (
        supabase.table("employees")
        .select(
            "id, company_id, first_name, last_name, email, "
            "employment_status, user_id, job_title"
        )
        .eq("id", str(employee_id))
        .maybe_single()
        .execute()
    )
    data = getattr(response, "data", None) if response else None
    return dict(data) if data else None


def get_company_name(company_id: str) -> str:
    response = (
        supabase.table("companies")
        .select("company_name, raison_sociale")
        .eq("id", str(company_id))
        .maybe_single()
        .execute()
    )
    data = getattr(response, "data", None) if response else None
    if not data:
        return "votre entreprise"
    return data.get("company_name") or data.get("raison_sociale") or "votre entreprise"


# ----- Comptes auth (API admin — jamais exposée au client) -----


class EmailAlreadyRegisteredError(Exception):
    """L'adresse porte déjà un compte auth — jamais écrasé sur simple e-mail."""


def create_auth_user(email: str, password: str) -> str:
    """Création confirmée d'office : le salarié vient de prouver son adresse.

    Création DIRECTE, jamais de recherche préalable par e-mail : le seul
    compte qu'une activation a le droit de modifier est celui déjà lié à la
    fiche (employees.user_id). Un conflit d'adresse sort en erreur dédiée.
    """
    try:
        response = supabase.auth.admin.create_user(
            {
                "email": email,
                "password": password,
                "email_confirm": True,
            }
        )
    except Exception as exc:  # AuthApiError : code email_exists / 422
        message = str(exc).lower()
        if "already" in message or "email_exists" in message:
            raise EmailAlreadyRegisteredError(str(exc)) from exc
        raise
    if response.user is None:
        raise RuntimeError("Création du compte impossible")
    return str(response.user.id)


def update_auth_user_password(user_id: str, password: str) -> None:
    supabase.auth.admin.update_user_by_id(
        str(user_id), {"password": password, "email_confirm": True}
    )


# ----- Câblage compte ↔ salarié -----


def ensure_profile(user_id: str, employee: Dict[str, Any]) -> None:
    """Crée le profil s'il n'existe pas. N'écrase JAMAIS un profil existant."""
    existing = (
        supabase.table("profiles")
        .select("id")
        .eq("id", str(user_id))
        .maybe_single()
        .execute()
    )
    if getattr(existing, "data", None):
        return
    (
        supabase.table("profiles")
        .insert(
            {
                "id": str(user_id),
                "first_name": employee.get("first_name") or "",
                "last_name": employee.get("last_name") or "",
                "role": "collaborateur",
                "company_id": str(employee["company_id"]),
                "job_title": employee.get("job_title") or "",
            }
        )
        .execute()
    )


def ensure_company_access(user_id: str, company_id: str) -> None:
    """
    Lie le compte à l'entreprise dans user_company_accesses (requis par
    get_current_user), template collaborateur — uniquement si aucun accès
    n'existe déjà (on ne touche pas au rôle d'un compte déjà relié).
    """
    from app.modules.users.application.service import (
        copy_template_permissions_to_user,
        get_default_system_template_id,
        get_user_company_access_repository,
    )

    access_repo = get_user_company_access_repository()
    if access_repo.get_by_user_and_company(str(user_id), str(company_id)):
        return

    template_id = get_default_system_template_id("collaborateur")
    access_data: Dict[str, Any] = {
        "user_id": str(user_id),
        "company_id": str(company_id),
        "role": "collaborateur",
        "is_primary": True,
    }
    if template_id:
        access_data["role_template_id"] = str(template_id)
    access_repo.create(access_data)

    if template_id:
        try:
            copy_template_permissions_to_user(
                str(template_id), str(user_id), str(company_id), str(user_id)
            )
        except Exception:
            logger.warning(
                "Activation : copie des permissions template échouée pour %s",
                user_id,
                exc_info=True,
            )


def link_employee_to_user(employee_id: str, user_id: str) -> None:
    """Liaison explicite employees.user_id — la branche 1 de la résolution."""
    (
        supabase.table("employees")
        .update({"user_id": str(user_id)})
        .eq("id", str(employee_id))
        .execute()
    )
