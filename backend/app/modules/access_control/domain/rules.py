"""
Règles métier pures pour le contrôle d'accès : hiérarchie des rôles,
rôles "viewable" par un créateur, etc.

Aucune dépendance à la base ni à FastAPI. Utilisées par le service
d'autorisation (application/service.py).
"""

from __future__ import annotations

# Hiérarchie : un rôle peut créer/modifier uniquement des rôles strictement inférieurs.
# custom n'a pas de position fixe ; ses droits dépendent des permissions.
ROLE_HIERARCHY: dict[str, list[str]] = {
    "admin": ["rh", "collaborateur_rh", "collaborateur", "custom"],
    "rh": ["collaborateur_rh", "collaborateur", "custom"],
    "collaborateur_rh": ["collaborateur"],
    "collaborateur": [],
    "custom": [],  # à affiner selon permissions
}


def can_assign_role(creator_role: str, target_role: str) -> bool:
    """
    Retourne True si le créateur (creator_role) peut attribuer target_role.
    Pure, sans I/O.
    """
    if creator_role == "super_admin":
        return True
    return target_role in ROLE_HIERARCHY.get(creator_role, [])


def get_viewable_roles(creator_role: str) -> list[str]:
    """
    Liste des rôles que le créateur peut « voir » (ex. pour afficher
    les permissions d'un utilisateur). Aligné sur user_management.py.
    """
    if creator_role == "admin":
        return ["admin", "rh", "collaborateur_rh", "collaborateur", "custom"]
    if creator_role == "rh":
        return ["rh", "collaborateur_rh", "collaborateur", "custom"]
    if creator_role == "collaborateur_rh":
        return ["collaborateur_rh", "collaborateur"]
    return []


def role_has_rh_level(role: str) -> bool:
    """
    True si le rôle a un niveau RH (admin, rh, collaborateur_rh).
    Règle pure, sans I/O. Utilisée pour can_access_company_as_rh (custom nécessite la persistance).
    """
    return role in ("admin", "rh", "collaborateur_rh")
