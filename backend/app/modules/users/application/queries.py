"""
Requêtes (cas d'usage lecture) du module users.

Délègue à l'infrastructure (queries, repository, mappers) et au domain (règles viewable/editable).
Comportement identique aux anciens routers.
"""
from typing import List, Optional

from app.modules.users.application.service import (
    get_auth_provider,
    get_company_repository,
    get_user_company_access_repository,
    get_user_permission_repository,
    get_user_repository,
)
from app.modules.users.domain import rules as domain_rules
from app.modules.users.infrastructure import queries as infra_queries
from app.modules.users.infrastructure.mappers import (
    row_to_company_access,
    row_to_company_access_super_admin,
    row_to_user_detail,
)
from app.modules.users.schemas.responses import CompanyAccess, User, UserDetail


def get_my_companies(current_user: User) -> List[CompanyAccess]:
    if current_user.is_super_admin:
        rows = infra_queries.fetch_active_companies_with_groups()
        return [row_to_company_access_super_admin(c) for c in rows]
    return current_user.accessible_companies


def get_me(current_user: User) -> User:
    return current_user


def get_user_company_accesses(user_id: str, current_user: User) -> List[CompanyAccess]:
    if not current_user.is_super_admin and user_id != current_user.id:
        target_ids = infra_queries.fetch_target_user_company_ids(user_id)
        if not any(current_user.is_admin_in_company(cid) for cid in target_ids):
            raise PermissionError("Vous n'avez pas les permissions pour voir ces accès")

    accesses = infra_queries.fetch_user_accesses_with_companies(user_id)
    return [
        row_to_company_access(acc, acc.get("companies"))
        for acc in accesses
        if acc.get("companies")
    ]


def get_company_users(
    company_id: str, role: Optional[str], current_user: User
) -> List[UserDetail]:
    rows = infra_queries.fetch_company_users_rows(company_id, role)
    auth = get_auth_provider()

    if current_user.is_super_admin:
        viewable_roles = ["admin", "rh", "collaborateur_rh", "collaborateur", "custom"]
        editable_roles = ["admin", "rh", "collaborateur_rh", "collaborateur", "custom"]
    else:
        creator_role = current_user.get_role_in_company(company_id) or ""
        viewable_roles = domain_rules.get_viewable_roles(creator_role)
        editable_roles = domain_rules.get_editable_roles(creator_role)

    users = []
    for row in rows:
        profile = row.get("profiles")
        if not profile:
            continue
        user_role = row["role"]
        if user_role not in viewable_roles:
            continue
        try:
            u = auth.get_user_by_id(profile["id"])
            email = u.user.email if u and u.user else "email@unknown.com"
        except Exception:
            email = "email@unknown.com"
        can_edit = user_role in editable_roles
        users.append(
            row_to_user_detail(row, profile, email, company_id, can_edit)
        )
    return users


def get_accessible_companies_for_user_creation(current_user: User) -> List[dict]:
    if current_user.is_super_admin:
        rows = infra_queries.fetch_active_companies_for_creation()
        return [
            {
                "company_id": row["id"],
                "company_name": row["company_name"],
                "creator_role": "super_admin",
                "can_create_roles": ["admin", "rh", "collaborateur_rh", "collaborateur", "custom"],
            }
            for row in rows
        ]

    company_repo = get_company_repository()
    companies_list = []
    for access in current_user.accessible_companies:
        creator_role = access.role
        can_create_roles = domain_rules.get_can_create_roles(creator_role)
        if can_create_roles:
            company_name = company_repo.get_name(str(access.company_id)) or "Entreprise"
            companies_list.append({
                "company_id": str(access.company_id),
                "company_name": company_name,
                "creator_role": creator_role,
                "can_create_roles": can_create_roles,
            })
    return companies_list


def get_user_detail(user_id: str, company_id: str, current_user: User) -> dict:
    access_repo = get_user_company_access_repository()
    user_repo = get_user_repository()
    perm_repo = get_user_permission_repository()
    auth = get_auth_provider()

    access = access_repo.get_by_user_and_company_with_template(user_id, company_id)
    if not access:
        raise LookupError("Utilisateur n'a pas d'accès à cette entreprise")
    target_role = access["role"]

    if not current_user.is_super_admin:
        if not current_user.has_access_to_company(company_id):
            raise PermissionError("Vous n'avez pas accès à cette entreprise")
        creator_role = current_user.get_role_in_company(company_id) or ""
        viewable_roles = domain_rules.get_viewable_roles(creator_role)
        editable_roles = domain_rules.get_editable_roles(creator_role)
        if target_role not in viewable_roles:
            raise PermissionError("Vous ne pouvez pas voir cet utilisateur")
        can_edit = target_role in editable_roles
    else:
        can_edit = True

    profile = user_repo.get_by_id(user_id)
    if not profile:
        raise LookupError("Profil utilisateur non trouvé")

    try:
        u = auth.get_user_by_id(user_id)
        email = u.user.email if u and u.user else "email@unknown.com"
    except Exception:
        email = "email@unknown.com"

    role_template_id = access.get("role_template_id")
    permission_ids = perm_repo.get_permission_ids(user_id, company_id, role_template_id)

    return {
        "id": user_id,
        "email": email,
        "first_name": profile["first_name"],
        "last_name": profile["last_name"],
        "job_title": profile.get("job_title"),
        "company_id": company_id,
        "role": target_role,
        "role_template_id": role_template_id,
        "role_template_name": (access.get("role_templates") or {}).get("name"),
        "permission_ids": permission_ids,
        "can_edit": can_edit,
    }
