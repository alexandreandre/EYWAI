"""
Règles métier pures du domaine promotions.

Logique extraite du legacy (services.promotion_service) pour préparer la migration.
Pas de dépendance à l'infrastructure.
"""
from __future__ import annotations

from typing import List, Optional

from app.modules.promotions.domain.enums import RhAccessRole


def validate_rh_access_transition(
    current_role: Optional[str],
    new_role: RhAccessRole,
) -> bool:
    """
    Valide qu'une transition de rôle RH est autorisée.

    Transitions autorisées:
    - null (aucun accès) → collaborateur_rh, rh
    - collaborateur_rh → rh, admin
    - rh → admin
    - admin → (pas de changement, déjà au maximum)
    """
    if current_role is None or current_role not in ("collaborateur_rh", "rh", "admin"):
        return new_role in ("collaborateur_rh", "rh")
    if current_role == "collaborateur_rh":
        return new_role in ("rh", "admin")
    if current_role == "rh":
        return new_role == "admin"
    if current_role == "admin":
        return False
    return False


def get_available_rh_roles(current_role: Optional[str]) -> List[RhAccessRole]:
    """Détermine les rôles RH disponibles selon le rôle actuel."""
    if current_role is None or current_role not in ("collaborateur_rh", "rh", "admin"):
        return ["collaborateur_rh", "rh"]
    if current_role == "collaborateur_rh":
        return ["rh", "admin"]
    if current_role == "rh":
        return ["admin"]
    return []


__all__ = ["validate_rh_access_transition", "get_available_rh_roles"]
