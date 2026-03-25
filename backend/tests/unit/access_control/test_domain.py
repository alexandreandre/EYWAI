"""
Tests unitaires du domain access_control : règles métier, enums.

Sans DB, sans HTTP. Couvre rules (can_assign_role, get_viewable_roles, role_has_rh_level),
ROLE_HIERARCHY et RoleKind.
"""

from app.modules.access_control.domain.enums import RoleKind
from app.modules.access_control.domain.rules import (
    ROLE_HIERARCHY,
    can_assign_role,
    get_viewable_roles,
    role_has_rh_level,
)


class TestRoleKind:
    """Enum des rôles utilisateur."""

    def test_role_kind_values(self):
        """Tous les rôles attendus sont définis."""
        assert RoleKind.SUPER_ADMIN == "super_admin"
        assert RoleKind.ADMIN == "admin"
        assert RoleKind.RH == "rh"
        assert RoleKind.COLLABORATEUR_RH == "collaborateur_rh"
        assert RoleKind.COLLABORATEUR == "collaborateur"
        assert RoleKind.CUSTOM == "custom"

    def test_role_kind_is_str_enum(self):
        """RoleKind hérite de StrEnum, valeurs comparables en str."""
        assert str(RoleKind.ADMIN) == "admin"
        assert RoleKind.RH == "rh"


class TestROLE_HIERARCHY:
    """Constante hiérarchie des rôles."""

    def test_admin_can_assign_all_lower_roles(self):
        """Admin peut attribuer rh, collaborateur_rh, collaborateur, custom."""
        assert "admin" in ROLE_HIERARCHY
        subs = ROLE_HIERARCHY["admin"]
        assert "rh" in subs
        assert "collaborateur_rh" in subs
        assert "collaborateur" in subs
        assert "custom" in subs

    def test_rh_can_assign_collaborateur_roles_and_custom(self):
        """RH peut attribuer collaborateur_rh, collaborateur, custom."""
        assert "rh" in ROLE_HIERARCHY
        assert "collaborateur_rh" in ROLE_HIERARCHY["rh"]
        assert "collaborateur" in ROLE_HIERARCHY["rh"]
        assert "custom" in ROLE_HIERARCHY["rh"]

    def test_collaborateur_rh_can_assign_only_collaborateur(self):
        """Collaborateur_rh ne peut attribuer que collaborateur."""
        assert ROLE_HIERARCHY["collaborateur_rh"] == ["collaborateur"]

    def test_collaborateur_and_custom_cannot_assign_any(self):
        """Collaborateur et custom ne peuvent attribuer aucun rôle."""
        assert ROLE_HIERARCHY["collaborateur"] == []
        assert ROLE_HIERARCHY["custom"] == []


class TestCanAssignRole:
    """Règle : un créateur peut-il attribuer le rôle cible ?"""

    def test_super_admin_can_assign_any_role(self):
        """super_admin peut attribuer n'importe quel rôle."""
        assert can_assign_role("super_admin", "admin") is True
        assert can_assign_role("super_admin", "rh") is True
        assert can_assign_role("super_admin", "collaborateur") is True
        assert can_assign_role("super_admin", "custom") is True

    def test_admin_can_assign_rh_and_below(self):
        """admin peut attribuer rh, collaborateur_rh, collaborateur, custom."""
        assert can_assign_role("admin", "rh") is True
        assert can_assign_role("admin", "collaborateur_rh") is True
        assert can_assign_role("admin", "collaborateur") is True
        assert can_assign_role("admin", "custom") is True
        assert can_assign_role("admin", "admin") is False

    def test_rh_can_assign_collaborateur_roles(self):
        """rh peut attribuer collaborateur_rh, collaborateur, custom."""
        assert can_assign_role("rh", "collaborateur_rh") is True
        assert can_assign_role("rh", "collaborateur") is True
        assert can_assign_role("rh", "custom") is True
        assert can_assign_role("rh", "admin") is False
        assert can_assign_role("rh", "rh") is False

    def test_collaborateur_rh_can_assign_only_collaborateur(self):
        """collaborateur_rh peut uniquement attribuer collaborateur."""
        assert can_assign_role("collaborateur_rh", "collaborateur") is True
        assert can_assign_role("collaborateur_rh", "rh") is False
        assert can_assign_role("collaborateur_rh", "custom") is False

    def test_collaborateur_cannot_assign_any(self):
        """collaborateur ne peut attribuer aucun rôle."""
        assert can_assign_role("collaborateur", "collaborateur") is False
        assert can_assign_role("collaborateur", "custom") is False

    def test_custom_cannot_assign_any(self):
        """custom ne peut attribuer aucun rôle (sans permission spécifique)."""
        assert can_assign_role("custom", "collaborateur") is False

    def test_unknown_creator_role_returns_false(self):
        """Rôle créateur inconnu → False (get retourne [])."""
        assert can_assign_role("unknown_role", "collaborateur") is False


class TestGetViewableRoles:
    """Rôles que le créateur peut « voir » (ex. pour afficher les permissions)."""

    def test_admin_sees_all_roles(self):
        """admin voit admin, rh, collaborateur_rh, collaborateur, custom."""
        roles = get_viewable_roles("admin")
        assert roles == ["admin", "rh", "collaborateur_rh", "collaborateur", "custom"]

    def test_rh_sees_rh_and_below(self):
        """rh voit rh, collaborateur_rh, collaborateur, custom."""
        roles = get_viewable_roles("rh")
        assert roles == ["rh", "collaborateur_rh", "collaborateur", "custom"]

    def test_collaborateur_rh_sees_two_roles(self):
        """collaborateur_rh voit collaborateur_rh et collaborateur."""
        roles = get_viewable_roles("collaborateur_rh")
        assert roles == ["collaborateur_rh", "collaborateur"]

    def test_other_roles_see_nothing(self):
        """collaborateur, custom, inconnu → liste vide."""
        assert get_viewable_roles("collaborateur") == []
        assert get_viewable_roles("custom") == []
        assert get_viewable_roles("unknown") == []


class TestRoleHasRhLevel:
    """True si le rôle a un niveau RH (admin, rh, collaborateur_rh)."""

    def test_rh_level_roles(self):
        """admin, rh, collaborateur_rh ont un niveau RH."""
        assert role_has_rh_level("admin") is True
        assert role_has_rh_level("rh") is True
        assert role_has_rh_level("collaborateur_rh") is True

    def test_non_rh_roles(self):
        """collaborateur et custom n'ont pas de niveau RH (sans persistance)."""
        assert role_has_rh_level("collaborateur") is False
        assert role_has_rh_level("custom") is False

    def test_unknown_role(self):
        """Rôle inconnu → False."""
        assert role_has_rh_level("unknown") is False

    def test_empty_string(self):
        """Chaîne vide → False."""
        assert role_has_rh_level("") is False
