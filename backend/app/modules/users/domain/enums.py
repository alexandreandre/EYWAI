"""
Enums du domaine users.

À migrer / aligner avec les rôles utilisés dans api/routers/users.py,
user_creation.py, user_management.py (admin, rh, collaborateur_rh, collaborateur, custom).
"""
from enum import StrEnum


class UserRole(StrEnum):
    """Rôles utilisateur par entreprise (aligné legacy)."""
    ADMIN = "admin"
    RH = "rh"
    COLLABORATEUR_RH = "collaborateur_rh"
    COLLABORATEUR = "collaborateur"
    CUSTOM = "custom"
