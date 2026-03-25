"""
Commandes (cas d'usage écriture) du module users.

Délègue au domain (règles) et à l'infrastructure (repositories, providers).
Comportement identique. Lève PermissionError (403), LookupError (404), ValueError (400).
"""

import traceback
from typing import Any, Optional

from app.modules.users.application.dto import (
    CreateUserResult,
    GrantAccessResult,
    RevokeAccessResult,
    SetPrimaryCompanyResult,
    UpdateAccessResult,
    UpdateUserResult,
)
from app.modules.users.application.service import (
    copy_template_permissions_to_user,
    get_auth_provider,
    get_company_repository,
    get_credentials_pdf_provider,
    get_default_system_template_id,
    get_storage_provider,
    get_user_company_access_repository,
    get_user_permission_repository,
    get_user_repository,
)
from app.modules.users.domain import rules as domain_rules


def set_primary_company(
    user_id: str, company_id: str, current_user: Any
) -> SetPrimaryCompanyResult:
    """Définit l'entreprise primaire. Vérifier has_access_to_company côté appelant."""
    repo = get_user_company_access_repository()
    repo.set_primary(user_id, company_id)
    # Vérifier que l'accès existe (set_primary a fait update, pas de retour)
    access = repo.get_by_user_and_company(user_id, company_id)
    if not access:
        raise LookupError("Accès non trouvé")
    return SetPrimaryCompanyResult(
        message="Entreprise primaire mise à jour avec succès",
        company_id=company_id,
    )


def grant_company_access_by_email(
    user_email: str, company_id: str, role: str, is_primary: bool, current_user: Any
) -> GrantAccessResult:
    """Accorde l'accès par email."""
    user_repo = get_user_repository()
    access_repo = get_user_company_access_repository()
    company_repo = get_company_repository()

    profile = user_repo.get_by_email(user_email)
    if not profile:
        raise LookupError(f"Utilisateur non trouvé: {user_email}")
    target_user_id = profile["id"]

    if not company_repo.get_name(company_id):
        raise LookupError(f"Entreprise non trouvée: {company_id}")

    access_data = {
        "user_id": target_user_id,
        "company_id": company_id,
        "role": role,
        "is_primary": is_primary,
    }
    existing = access_repo.get_by_user_and_company(target_user_id, company_id)
    if existing:
        result = access_repo.update(
            target_user_id, company_id, {"role": role, "is_primary": is_primary}
        )
        message = "Accès mis à jour avec succès"
    else:
        result = access_repo.create(access_data)
        message = "Accès accordé avec succès"
    return GrantAccessResult(
        message=message,
        access=result if result else None,
    )


def grant_company_access_by_user_id(
    user_id: str, company_id: str, role: str, is_primary: bool, current_user: Any
) -> GrantAccessResult:
    """Accorde l'accès par user_id."""
    user_repo = get_user_repository()
    access_repo = get_user_company_access_repository()
    company_repo = get_company_repository()
    target_user_id = str(user_id)

    if not user_repo.get_by_id(target_user_id):
        raise LookupError(f"Utilisateur non trouvé: {target_user_id}")
    if not company_repo.get_name(company_id):
        raise LookupError(f"Entreprise non trouvée: {company_id}")

    access_data = {
        "user_id": target_user_id,
        "company_id": company_id,
        "role": role,
        "is_primary": is_primary,
    }
    existing = access_repo.get_by_user_and_company(target_user_id, company_id)
    if existing:
        result = access_repo.update(
            target_user_id, company_id, {"role": role, "is_primary": is_primary}
        )
        message = "Accès mis à jour avec succès"
    else:
        result = access_repo.create(access_data)
        message = "Accès accordé avec succès"
    return GrantAccessResult(
        message=message,
        access=result if result else None,
    )


def revoke_company_access(
    user_id: str, company_id: str, current_user: Any
) -> RevokeAccessResult:
    """Révoque l'accès. Vérification admin côté appelant."""
    access_repo = get_user_company_access_repository()
    domain_rules.validate_cannot_revoke_last_admin(
        is_revoking_self=(
            user_id == current_user.id
            and not getattr(current_user, "is_super_admin", False)
        ),
        admin_count=access_repo.count_admins(company_id),
    )
    result = access_repo.delete(user_id, company_id)
    if result is None:
        raise LookupError("Accès non trouvé")
    return RevokeAccessResult(
        message="Accès révoqué avec succès",
        user_id=user_id,
        company_id=company_id,
    )


def update_company_access(
    user_id: str,
    company_id: str,
    role: Optional[str],
    is_primary: Optional[bool],
    current_user: Any,
) -> UpdateAccessResult:
    """Modifie l'accès (rôle ou is_primary). Vérification admin côté appelant."""
    if role is None and is_primary is None:
        raise ValueError("Aucune modification fournie")
    update_data = {}
    if role is not None:
        update_data["role"] = role
    if is_primary is not None:
        update_data["is_primary"] = is_primary
    access_repo = get_user_company_access_repository()
    result = access_repo.update(user_id, company_id, update_data)
    if not result:
        raise LookupError("Accès non trouvé")
    return UpdateAccessResult(message="Accès mis à jour avec succès", access=result)


def create_user_with_permissions(data: Any, current_user: Any) -> CreateUserResult:
    """
    Crée un utilisateur (auth + profil + accès + permissions + PDF si rôle RH).
    Vérifications primaire et hiérarchie à faire côté appelant.
    """
    from app.shared.utils import remove_accents

    primary_accesses = [a for a in data.company_accesses if a.is_primary]
    domain_rules.validate_one_primary_access(len(primary_accesses))

    auth = get_auth_provider()
    try:
        r = auth.create_user(
            data.email,
            data.password,
            {
                "first_name": data.first_name,
                "last_name": data.last_name,
                "job_title": data.job_title,
            },
        )
        user_id = r.user.id
    except Exception as e:
        raise ValueError(f"Erreur lors de la création de l'utilisateur: {e}") from e

    user_repo = get_user_repository()
    access_repo = get_user_company_access_repository()
    perm_repo = get_user_permission_repository()
    try:
        primary_access = primary_accesses[0]
        user_repo.create(
            {
                "id": user_id,
                "first_name": data.first_name,
                "last_name": data.last_name,
                "job_title": data.job_title,
                "company_id": str(primary_access.company_id),
                "role": primary_access.base_role,
            }
        )

        for access in data.company_accesses:
            company_id = str(access.company_id)
            access_data = {
                "user_id": user_id,
                "company_id": company_id,
                "role": access.base_role,
                "is_primary": access.is_primary,
                "role_template_id": str(access.role_template_id)
                if access.role_template_id
                else None,
            }
            if getattr(access, "contract_type", None):
                access_data["contract_type"] = access.contract_type
            if getattr(access, "statut", None):
                access_data["statut"] = access.statut
            access_repo.create(access_data)

            template_id_to_use = access.role_template_id
            if access.base_role == "custom" and not template_id_to_use:
                try:
                    auth.delete_user(user_id)
                except Exception:
                    pass
                raise ValueError("Un role_template_id est requis pour les rôles custom")

            if not template_id_to_use and access.base_role != "custom":
                template_id_to_use = get_default_system_template_id(access.base_role)
                if template_id_to_use:
                    access_repo.update(
                        user_id, company_id, {"role_template_id": template_id_to_use}
                    )

            if template_id_to_use:
                copy_template_permissions_to_user(
                    str(template_id_to_use),
                    user_id,
                    company_id,
                    str(current_user.id),
                )
            for permission_id in access.permission_ids:
                perm_repo.upsert(
                    user_id, company_id, str(permission_id), str(current_user.id)
                )

        has_rh_role = any(
            acc.base_role in ("admin", "rh") for acc in data.company_accesses
        )
        if has_rh_role:
            try:
                pdf_provider = get_credentials_pdf_provider()
                storage = get_storage_provider()
                first_name_for_username = (
                    remove_accents(data.first_name).lower().replace(" ", "_")
                )
                last_name_for_username = (
                    remove_accents(data.last_name).lower().replace(" ", "_")
                )
                username = f"{first_name_for_username}.{last_name_for_username}"
                logo_path = pdf_provider.get_logo_path()
                pdf_content = pdf_provider.generate(
                    data.first_name,
                    data.last_name,
                    username,
                    data.password,
                    logo_path,
                )
                storage.upload_credentials_pdf(
                    str(primary_access.company_id), user_id, pdf_content
                )
            except Exception:
                traceback.print_exc()

        return CreateUserResult(
            message="Utilisateur créé avec succès",
            user_id=user_id,
            email=data.email,
            companies_count=len(data.company_accesses),
        )
    except Exception as e:
        try:
            auth.delete_user(user_id)
        except Exception:
            pass
        raise RuntimeError(
            f"Erreur lors de la configuration de l'utilisateur: {e}"
        ) from e


def update_user_with_permissions(
    user_id: str, data: Any, current_user: Any
) -> UpdateUserResult:
    """Modifie un utilisateur (profil, rôle, permissions)."""
    company_id = str(data.company_id)
    access_repo = get_user_company_access_repository()
    user_repo = get_user_repository()
    perm_repo = get_user_permission_repository()

    if not access_repo.get_by_user_and_company(user_id, company_id):
        raise LookupError("Utilisateur n'a pas d'accès à cette entreprise")

    profile_updates = {}
    if data.first_name:
        profile_updates["first_name"] = data.first_name
    if data.last_name:
        profile_updates["last_name"] = data.last_name
    if data.job_title is not None:
        profile_updates["job_title"] = data.job_title
    if profile_updates:
        user_repo.update(user_id, profile_updates)

    if data.base_role:
        access_repo.update(
            user_id,
            company_id,
            {
                "role": data.base_role,
                "role_template_id": str(data.role_template_id)
                if data.role_template_id
                else None,
            },
        )

    if data.permission_ids is not None:
        perm_repo.delete_for_user_company(user_id, company_id)
        if data.role_template_id:
            copy_template_permissions_to_user(
                str(data.role_template_id),
                user_id,
                company_id,
                str(current_user.id),
            )
        for permission_id in data.permission_ids:
            perm_repo.upsert(
                user_id, company_id, str(permission_id), str(current_user.id)
            )

    return UpdateUserResult(message="Utilisateur modifié avec succès", user_id=user_id)
