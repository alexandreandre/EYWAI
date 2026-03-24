"""
Orchestration et helpers du module company_groups.

Résolution des company_ids accessibles, résolution des company_ids d'un groupe,
vérifications d'autorisation (déléguées au router ou utilisées par commands/queries).
Comportement identique à api/routers/company_groups.py.
"""
from __future__ import annotations

from typing import Any, List

from app.modules.company_groups.infrastructure.repository import company_group_repository


def get_accessible_company_ids(current_user: Any) -> List[str]:
    """
    Retourne les IDs d'entreprises accessibles par l'utilisateur.
    Pour super_admin : retourne [] (convention : pas de filtre, tout est accessible).
    """
    if getattr(current_user, "is_super_admin", False):
        return []
    acc = getattr(current_user, "accessible_companies", None) or []
    return [a.company_id for a in acc]


def get_company_ids_for_group(
    group_id: str, current_user: Any
) -> List[str]:
    """
    Retourne les IDs d'entreprises du groupe accessibles par l'utilisateur.
    Super_admin : toutes les entreprises du groupe.
    Sinon : intersection avec accessible_companies.
    """
    all_ids = company_group_repository.get_company_ids_by_group_id(group_id)
    if not all_ids:
        return []
    if getattr(current_user, "is_super_admin", False):
        return all_ids
    accessible = set(get_accessible_company_ids(current_user))
    return [cid for cid in all_ids if cid in accessible]


def get_group_company_ids_for_permission_check(group_id: str) -> List[str]:
    """
    Retourne les IDs de toutes les entreprises du groupe (pour vérification admin).
    Utilisé par le router pour update_group (super_admin ou admin de toutes).
    """
    return company_group_repository.get_group_company_ids_for_permission_check(
        group_id
    )


def filter_companies_by_access(
    companies: List[dict], accessible_company_ids: List[str]
) -> List[dict]:
    """Filtre les entreprises par accès. Si accessible_company_ids vide (super_admin), retourne tout."""
    if not accessible_company_ids:
        return companies
    acc_set = set(accessible_company_ids)
    return [c for c in companies if c.get("id") in acc_set]
