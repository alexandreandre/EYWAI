"""
Règles métier pures du module users.

Aucune dépendance à la DB, FastAPI ou infrastructure.
Comportement aligné sur api/routers/users.py et user_creation.py.
"""

from typing import Any, List

# Hiérarchie des rôles : qui peut créer/modifier quel rôle (aligné legacy)
ROLE_HIERARCHY = {
    "admin": ["rh", "collaborateur_rh", "collaborateur", "custom"],
    "rh": ["collaborateur_rh", "collaborateur", "custom"],
    "collaborateur_rh": ["collaborateur"],
    "collaborateur": [],
}


def check_role_hierarchy(creator_user: Any, target_role: str, company_id: str) -> bool:
    """
    Vérifie si le créateur peut créer/modifier un utilisateur avec le rôle cible.
    creator_user doit exposer : is_super_admin, get_role_in_company(company_id) -> str | None.
    """
    if getattr(creator_user, "is_super_admin", False):
        return True
    creator_role = None
    if hasattr(creator_user, "get_role_in_company"):
        get_role = creator_user.get_role_in_company
        try:
            creator_role = get_role(company_id)
        except TypeError:
            # Compat tests/doublures: certaines implémentations ignorent company_id.
            creator_role = get_role()
    if not creator_role:
        return False
    return target_role in ROLE_HIERARCHY.get(creator_role, [])


def get_viewable_roles(creator_role: str) -> List[str]:
    """Rôles que l'utilisateur peut voir selon son rôle (pour get_company_users, get_user_detail)."""
    if creator_role == "admin":
        return ["admin", "rh", "collaborateur_rh", "collaborateur", "custom"]
    if creator_role == "rh":
        return ["rh", "collaborateur_rh", "collaborateur", "custom"]
    if creator_role == "collaborateur_rh":
        return ["collaborateur_rh", "collaborateur"]
    return []


def get_editable_roles(creator_role: str) -> List[str]:
    """Rôles que l'utilisateur peut modifier (strictement inférieurs)."""
    if creator_role == "admin":
        return ["rh", "collaborateur_rh", "collaborateur", "custom"]
    if creator_role == "rh":
        return ["collaborateur_rh", "collaborateur", "custom"]
    if creator_role == "collaborateur_rh":
        return ["collaborateur"]
    return []


def get_can_create_roles(creator_role: str) -> List[str]:
    """Rôles que l'utilisateur peut créer (pour accessible-companies)."""
    return get_editable_roles(creator_role)


def validate_one_primary_access(primary_count: int) -> None:
    """
    Lève ValueError si primary_count != 1 (à la création : exactement un accès primaire).
    """
    if primary_count == 0:
        raise ValueError("Au moins un accès doit être marqué comme primaire")
    if primary_count > 1:
        raise ValueError("Un seul accès peut être marqué comme primaire")


def validate_cannot_revoke_last_admin(is_revoking_self: bool, admin_count: int) -> None:
    """Lève ValueError si l'utilisateur révoque son propre accès et est le dernier admin."""
    if is_revoking_self and admin_count <= 1:
        raise ValueError(
            "Vous ne pouvez pas révoquer votre propre accès car vous êtes le dernier admin"
        )
