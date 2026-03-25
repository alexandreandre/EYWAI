"""
Rôles et niveaux d'accès pour le contrôle d'accès.

À terme : aligné sur les rôles utilisés dans user_company_accesses et
les permissions granulaires (schemas.permissions). Ne pas déplacer
les enums métier des autres modules ici ; ce module centralise uniquement
le vocabulaire commun (rôles, hiérarchie).
"""

from enum import StrEnum


class RoleKind(StrEnum):
    """Rôles utilisateur dans une entreprise (base_role)."""

    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    RH = "rh"
    COLLABORATEUR_RH = "collaborateur_rh"
    COLLABORATEUR = "collaborateur"
    CUSTOM = "custom"
