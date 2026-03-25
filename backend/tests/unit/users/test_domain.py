"""
Tests unitaires du domaine users : entités, value objects, règles, enums.

Sans DB, sans HTTP. Couvre domain/enums.py et domain/rules.py.
Le module n'a pas d'entités/value objects instanciables (placeholders).
"""

import pytest

from app.modules.users.domain.enums import UserRole
from app.modules.users.domain import rules as domain_rules


pytestmark = pytest.mark.unit


# ----- Enums -----


class TestUserRole:
    """UserRole (StrEnum) : valeurs alignées legacy."""

    def test_admin_value(self):
        assert UserRole.ADMIN == "admin"

    def test_rh_value(self):
        assert UserRole.RH == "rh"

    def test_collaborateur_rh_value(self):
        assert UserRole.COLLABORATEUR_RH == "collaborateur_rh"

    def test_collaborateur_value(self):
        assert UserRole.COLLABORATEUR == "collaborateur"

    def test_custom_value(self):
        assert UserRole.CUSTOM == "custom"

    def test_all_roles_are_strings(self):
        for role in UserRole:
            assert isinstance(role, str)


# ----- Règles : hiérarchie des rôles -----


class TestCheckRoleHierarchy:
    """check_role_hierarchy(creator_user, target_role, company_id)."""

    def test_super_admin_can_assign_any_role(self):
        creator = type(
            "User",
            (),
            {"is_super_admin": True, "get_role_in_company": lambda self, c: None},
        )()
        assert domain_rules.check_role_hierarchy(creator, "admin", "c1") is True
        assert domain_rules.check_role_hierarchy(creator, "rh", "c1") is True
        assert domain_rules.check_role_hierarchy(creator, "collaborateur", "c1") is True

    def test_admin_can_assign_rh_collaborateur_custom(self):
        def get_role(_company_id):
            return "admin"

        creator = type(
            "User", (), {"is_super_admin": False, "get_role_in_company": get_role}
        )()
        assert domain_rules.check_role_hierarchy(creator, "rh", "c1") is True
        assert (
            domain_rules.check_role_hierarchy(creator, "collaborateur_rh", "c1") is True
        )
        assert domain_rules.check_role_hierarchy(creator, "collaborateur", "c1") is True
        assert domain_rules.check_role_hierarchy(creator, "custom", "c1") is True

    def test_admin_cannot_assign_admin(self):
        def get_role(_company_id):
            return "admin"

        creator = type(
            "User", (), {"is_super_admin": False, "get_role_in_company": get_role}
        )()
        assert domain_rules.check_role_hierarchy(creator, "admin", "c1") is False

    def test_rh_can_assign_collaborateur_roles_only(self):
        def get_role(_company_id):
            return "rh"

        creator = type(
            "User", (), {"is_super_admin": False, "get_role_in_company": get_role}
        )()
        assert (
            domain_rules.check_role_hierarchy(creator, "collaborateur_rh", "c1") is True
        )
        assert domain_rules.check_role_hierarchy(creator, "collaborateur", "c1") is True
        assert domain_rules.check_role_hierarchy(creator, "admin", "c1") is False
        assert domain_rules.check_role_hierarchy(creator, "rh", "c1") is False

    def test_collaborateur_rh_can_assign_only_collaborateur(self):
        def get_role(_company_id):
            return "collaborateur_rh"

        creator = type(
            "User", (), {"is_super_admin": False, "get_role_in_company": get_role}
        )()
        assert domain_rules.check_role_hierarchy(creator, "collaborateur", "c1") is True
        assert domain_rules.check_role_hierarchy(creator, "rh", "c1") is False

    def test_collaborateur_can_assign_nothing(self):
        def get_role(_company_id):
            return "collaborateur"

        creator = type(
            "User", (), {"is_super_admin": False, "get_role_in_company": get_role}
        )()
        assert (
            domain_rules.check_role_hierarchy(creator, "collaborateur", "c1") is False
        )

    def test_no_creator_role_returns_false(self):
        creator = type(
            "User",
            (),
            {"is_super_admin": False, "get_role_in_company": lambda s, c: None},
        )()
        assert domain_rules.check_role_hierarchy(creator, "rh", "c1") is False

    def test_creator_without_get_role_in_company_returns_false(self):
        creator = type("User", (), {"is_super_admin": False})()
        assert domain_rules.check_role_hierarchy(creator, "rh", "c1") is False


class TestGetViewableRoles:
    """get_viewable_roles(creator_role) : rôles visibles selon le rôle du créateur."""

    def test_admin_sees_all(self):
        assert domain_rules.get_viewable_roles("admin") == [
            "admin",
            "rh",
            "collaborateur_rh",
            "collaborateur",
            "custom",
        ]

    def test_rh_sees_rh_and_below(self):
        assert domain_rules.get_viewable_roles("rh") == [
            "rh",
            "collaborateur_rh",
            "collaborateur",
            "custom",
        ]

    def test_collaborateur_rh_sees_two(self):
        assert domain_rules.get_viewable_roles("collaborateur_rh") == [
            "collaborateur_rh",
            "collaborateur",
        ]

    def test_collaborateur_sees_none(self):
        assert domain_rules.get_viewable_roles("collaborateur") == []


class TestGetEditableRoles:
    """get_editable_roles(creator_role) : rôles modifiables (strictement inférieurs)."""

    def test_admin_editable(self):
        assert domain_rules.get_editable_roles("admin") == [
            "rh",
            "collaborateur_rh",
            "collaborateur",
            "custom",
        ]

    def test_rh_editable(self):
        assert domain_rules.get_editable_roles("rh") == [
            "collaborateur_rh",
            "collaborateur",
            "custom",
        ]

    def test_collaborateur_rh_editable(self):
        assert domain_rules.get_editable_roles("collaborateur_rh") == ["collaborateur"]

    def test_collaborateur_editable_empty(self):
        assert domain_rules.get_editable_roles("collaborateur") == []


class TestGetCanCreateRoles:
    """get_can_create_roles(creator_role) = get_editable_roles."""

    def test_equals_editable_for_admin(self):
        assert domain_rules.get_can_create_roles(
            "admin"
        ) == domain_rules.get_editable_roles("admin")

    def test_equals_editable_for_rh(self):
        assert domain_rules.get_can_create_roles(
            "rh"
        ) == domain_rules.get_editable_roles("rh")


class TestValidateOnePrimaryAccess:
    """validate_one_primary_access(primary_count) : exactement un accès primaire."""

    def test_one_primary_ok(self):
        domain_rules.validate_one_primary_access(1)  # no raise

    def test_zero_primary_raises(self):
        with pytest.raises(ValueError) as exc_info:
            domain_rules.validate_one_primary_access(0)
        assert "Au moins un accès doit être marqué comme primaire" in str(
            exc_info.value
        )

    def test_two_primary_raises(self):
        with pytest.raises(ValueError) as exc_info:
            domain_rules.validate_one_primary_access(2)
        assert "Un seul accès peut être marqué comme primaire" in str(exc_info.value)


class TestValidateCannotRevokeLastAdmin:
    """validate_cannot_revoke_last_admin(is_revoking_self, admin_count)."""

    def test_revoking_self_when_last_admin_raises(self):
        with pytest.raises(ValueError) as exc_info:
            domain_rules.validate_cannot_revoke_last_admin(
                is_revoking_self=True, admin_count=1
            )
        assert "dernier admin" in str(exc_info.value).lower()

    def test_revoking_self_when_other_admins_ok(self):
        domain_rules.validate_cannot_revoke_last_admin(
            is_revoking_self=True, admin_count=2
        )  # no raise

    def test_revoking_other_user_ok_even_if_one_admin(self):
        domain_rules.validate_cannot_revoke_last_admin(
            is_revoking_self=False, admin_count=1
        )  # no raise
