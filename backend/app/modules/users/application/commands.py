"""
Commandes (cas d'usage écriture) du module users.

Délègue au domain (règles) et à l'infrastructure (repositories, providers).
Comportement identique. Lève PermissionError (403), LookupError (404), ValueError (400).
"""

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
    check_role_hierarchy,
    copy_template_permissions_to_user,
    get_auth_provider,
    get_company_repository,
    get_credentials_pdf_provider,
    get_default_system_template_id,
    get_role_template_repository,
    get_storage_provider,
    get_user_company_access_repository,
    get_user_permission_repository,
    get_user_repository,
)
from app.modules.employees.infrastructure.providers import get_company_reader
from app.modules.users.domain import rules as domain_rules

from app.core.logging import get_logger

logger = get_logger(__name__)


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


# Réponse unique, hors super-admin, quand la personne visée n'existe pas OU n'est
# pas gérée par l'appelant : la route ne dit pas si une adresse a un compte.
PERSONNE_HORS_PERIMETRE = (
    "Aucune personne que vous gérez ne correspond. Pour ouvrir une société à "
    "quelqu'un d'une autre société, demandez à un administrateur de la plateforme."
)
ACCES_PROPRE_INTERDIT = "Vous ne pouvez pas modifier votre propre accès."


def _est_admin_plateforme(current_user: Any) -> bool:
    return bool(getattr(current_user, "is_platform_admin", False))


def _roles_de_l_appelant(current_user: Any) -> dict:
    return {
        str(acces.company_id): acces.role
        for acces in getattr(current_user, "accessible_companies", []) or []
    }


def _verifier_personne_geree(current_user: Any, target_user_id: str) -> None:
    """Hors super-admin : on n'agit que sur soi (refusé) ou sur une personne gérée."""
    if _est_admin_plateforme(current_user):
        return
    if str(target_user_id) == str(current_user.id):
        raise PermissionError(ACCES_PROPRE_INTERDIT)
    acces = get_user_company_access_repository().get_access_roles_for_user(
        str(target_user_id)
    )
    if not domain_rules.peut_gerer_la_personne(
        _roles_de_l_appelant(current_user), acces
    ):
        raise LookupError(PERSONNE_HORS_PERIMETRE)


def _verifier_role_donnable(current_user: Any, role: str, company_id: str) -> None:
    if _est_admin_plateforme(current_user):
        return
    if not check_role_hierarchy(current_user, role, company_id):
        raise PermissionError(
            f"Vous ne pouvez pas donner le rôle '{role}' dans cette entreprise"
        )


def _verifier_droits_donnes(
    current_user: Any,
    company_id: str,
    permission_ids: Any,
    role_template_id: Any,
    deja: Any = (),
) -> None:
    """Droits fins donnés à une personne : jamais au-dessus du niveau de l'appelant.

    Hors super-admin : le modèle de rôle choisi est commun ou de cette société,
    et chaque permission ajoutée (directe ou venue du modèle) est d'un niveau
    inférieur ou égal au rôle de l'appelant. Les permissions déjà détenues ne
    comptent pas : on peut garder ce qu'un supérieur a donné.
    """
    if _est_admin_plateforme(current_user):
        return
    demandees = {str(p) for p in (permission_ids or [])}
    if role_template_id:
        tpl_repo = get_role_template_repository()
        modele = tpl_repo.get_company_scope(str(role_template_id))
        if (
            not modele
            or modele.get("is_active") is False
            or (modele.get("company_id") and str(modele["company_id"]) != str(company_id))
        ):
            raise PermissionError("Ce modèle de rôle n'est pas disponible dans cette société")
        demandees |= {str(p) for p in tpl_repo.get_template_permission_ids(str(role_template_id))}
    ajoutees = sorted(demandees - {str(p) for p in (deja or [])})
    if not ajoutees:
        return
    niveaux = get_user_permission_repository().get_required_roles_by_ids(ajoutees)
    role_appelant = current_user.get_role_in_company(company_id) or ""
    refusees = [
        pid
        for pid in ajoutees
        if pid not in niveaux
        or not domain_rules.niveau_de_permission_permis(role_appelant, niveaux[pid])
    ]
    if refusees:
        raise PermissionError(
            "Vous ne pouvez pas donner une permission d'un niveau supérieur au vôtre "
            f"({len(refusees)} refusée(s))."
        )


def _ouvrir_acces(
    target_user_id: str,
    company_id: str,
    role: str,
    is_primary: bool,
    current_user: Any,
) -> GrantAccessResult:
    """Crée l'accès d'une personne déjà vérifiée. N'écrase jamais un accès existant."""
    access_repo = get_user_company_access_repository()
    company_repo = get_company_repository()

    if not company_repo.get_name(company_id):
        raise LookupError(f"Entreprise non trouvée: {company_id}")

    existing = access_repo.get_by_user_and_company(target_user_id, company_id)
    if existing:
        # Jamais d'écrasement (relectures du 20/11 et du 24/11) : un octroi ne
        # change ni le rôle, ni la consultation, ni l'état d'un accès existant.
        if existing.get("is_active") is False:
            raise ValueError(
                "L'accès de cette personne à cette société a été coupé : seul un "
                "administrateur de la plateforme peut le rétablir."
            )
        raise ValueError(
            "Cette personne a déjà un accès à cette société : il se modifie depuis la société elle-même."
        )

    # La société d'arrivée d'une personne n'est pas le choix de qui lui ouvre un accès.
    if not _est_admin_plateforme(current_user):
        is_primary = False

    result = access_repo.create(
        {
            "user_id": target_user_id,
            "company_id": company_id,
            "role": role,
            "is_primary": is_primary,
        }
    )
    # Même geste qu'à la création d'un compte : le rôle de base reçoit les
    # droits de son modèle système, sinon l'accès serait vide de permissions.
    if role != "custom":
        template_id = get_default_system_template_id(role)
        if template_id:
            access_repo.update(
                target_user_id, company_id, {"role_template_id": template_id}
            )
            copy_template_permissions_to_user(
                str(template_id),
                target_user_id,
                company_id,
                str(current_user.id),
            )
    return GrantAccessResult(
        message="Accès accordé avec succès",
        access=result if result else None,
    )


def grant_company_access_by_email(
    user_email: str, company_id: str, role: str, is_primary: bool, current_user: Any
) -> GrantAccessResult:
    """Accorde l'accès par adresse, aux mêmes règles que par identifiant.

    Hors super-admin, une adresse inconnue et l'adresse d'une personne qu'on ne
    gère pas reçoivent la même réponse (pas d'énumération des comptes).
    """
    _verifier_role_donnable(current_user, role, company_id)
    profile = get_user_repository().get_by_email(user_email)
    if not profile:
        if _est_admin_plateforme(current_user):
            raise LookupError(f"Utilisateur non trouvé: {user_email}")
        raise LookupError(PERSONNE_HORS_PERIMETRE)
    target_user_id = str(profile["id"])
    _verifier_personne_geree(current_user, target_user_id)
    return _ouvrir_acces(target_user_id, company_id, role, is_primary, current_user)


def grant_company_access_by_user_id(
    user_id: str, company_id: str, role: str, is_primary: bool, current_user: Any
) -> GrantAccessResult:
    """Accorde l'accès par identifiant (« Donner accès à d'autres sociétés »)."""
    target_user_id = str(user_id)
    _verifier_role_donnable(current_user, role, company_id)
    if _est_admin_plateforme(current_user):
        if not get_user_repository().get_by_id(target_user_id):
            raise LookupError(f"Utilisateur non trouvé: {target_user_id}")
    else:
        _verifier_personne_geree(current_user, target_user_id)
    return _ouvrir_acces(target_user_id, company_id, role, is_primary, current_user)


def revoke_company_access(
    user_id: str, company_id: str, current_user: Any
) -> RevokeAccessResult:
    """Révoque l'accès. Vérification admin côté appelant.

    Hors super-admin, on ne retire que son propre accès (sauf dernier admin) ou
    celui d'une personne de rôle inférieur dans la société : un admin ne retire
    pas un autre admin.
    """
    access_repo = get_user_company_access_repository()
    if not _est_admin_plateforme(current_user) and str(user_id) != str(
        current_user.id
    ):
        cible = access_repo.get_by_user_and_company(user_id, company_id)
        if cible is None:
            raise LookupError("Accès non trouvé")
        role_appelant = current_user.get_role_in_company(company_id) or ""
        if cible.get("role") not in domain_rules.get_editable_roles(role_appelant):
            raise PermissionError(
                "Vous ne pouvez pas retirer l'accès d'une personne de rôle égal ou supérieur au vôtre."
            )
    domain_rules.validate_cannot_revoke_last_admin(
        is_revoking_self=(
            user_id == current_user.id
            and not getattr(current_user, "is_platform_admin", False)
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
    access_repo = get_user_company_access_repository()
    if not _est_admin_plateforme(current_user):
        # Mêmes règles que la modification d'un utilisateur : ni soi-même, ni
        # un pair ou un supérieur, ni un rôle au-dessus de check_role_hierarchy.
        if str(user_id) == str(current_user.id):
            raise PermissionError(ACCES_PROPRE_INTERDIT)
        cible = access_repo.get_by_user_and_company(user_id, company_id)
        if cible is None:
            raise LookupError("Accès non trouvé")
        role_appelant = current_user.get_role_in_company(company_id) or ""
        if cible.get("role") not in domain_rules.get_editable_roles(role_appelant):
            raise PermissionError(
                "Vous n'avez pas les droits pour modifier l'accès de cette personne"
            )
        if role is not None:
            _verifier_role_donnable(current_user, role, company_id)
    update_data = {}
    if role is not None:
        update_data["role"] = role
    if is_primary is not None:
        update_data["is_primary"] = is_primary
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
    for access in data.company_accesses:
        _verifier_droits_donnes(
            current_user,
            str(access.company_id),
            access.permission_ids,
            access.role_template_id,
        )

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
                company_reader = get_company_reader()
                company_data = company_reader.get_company_data(
                    str(primary_access.company_id)
                )
                pdf_content = pdf_provider.generate(
                    data.first_name,
                    data.last_name,
                    username,
                    data.password,
                    company_data=company_data,
                )
                storage.upload_credentials_pdf(
                    str(primary_access.company_id), user_id, pdf_content
                )
            except Exception:
                logger.exception("Échec de create_user_with_permissions")

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

    access = access_repo.get_by_user_and_company_with_template(user_id, company_id)
    if not access:
        raise LookupError("Utilisateur n'a pas d'accès à cette entreprise")
    target_role = access["role"]

    if not getattr(current_user, "is_platform_admin", False):
        if not current_user.has_access_to_company(company_id):
            raise PermissionError("Vous n'avez pas accès à cette entreprise")
        creator_role = current_user.get_role_in_company(company_id) or ""
        editable_roles = domain_rules.get_editable_roles(creator_role)
        if target_role not in editable_roles:
            raise PermissionError(
                "Vous n'avez pas les droits pour modifier cet utilisateur"
            )
        if data.base_role:
            new_role = data.base_role
            if new_role not in editable_roles:
                raise PermissionError(
                    f"Vous ne pouvez pas attribuer le rôle '{new_role}' dans cette entreprise"
                )
            if not check_role_hierarchy(current_user, new_role, company_id):
                raise PermissionError(
                    f"Vous ne pouvez pas créer d'utilisateurs avec le rôle '{new_role}' "
                    f"dans cette entreprise"
                )

    if data.permission_ids is not None or data.role_template_id:
        _verifier_droits_donnes(
            current_user,
            company_id,
            data.permission_ids,
            data.role_template_id,
            deja=perm_repo.get_permission_ids(user_id, company_id),
        )

    profile_updates = {}
    if data.first_name:
        profile_updates["first_name"] = data.first_name
    if data.last_name:
        profile_updates["last_name"] = data.last_name
    if data.job_title is not None:
        profile_updates["job_title"] = data.job_title
    if profile_updates:
        user_repo.update(user_id, profile_updates)

    # Persiste le rôle et/ou le template. On resynchronise role_template_id dès
    # qu'un édit de permissions est soumis (permission_ids fourni), même si le
    # rôle est inchangé — sinon un simple changement de template ne serait pas
    # stocké. On ne touche pas au template lors d'un update de profil seul.
    access_updates: dict = {}
    if data.base_role:
        access_updates["role"] = data.base_role
    if data.base_role or data.permission_ids is not None:
        access_updates["role_template_id"] = (
            str(data.role_template_id) if data.role_template_id else None
        )
    if access_updates:
        access_repo.update(user_id, company_id, access_updates)

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
