"""
Tests du domaine super_admin : entités, value objects, règles, enums, exceptions.

Sans DB, sans HTTP. Couvre domain/entities.py, value_objects.py, rules.py, enums.py, exceptions.py.
"""

from dataclasses import FrozenInstanceError
from datetime import datetime
from uuid import uuid4

import pytest

from app.modules.super_admin.domain.entities import SuperAdmin
from app.modules.super_admin.domain.value_objects import SuperAdminPermissions
from app.modules.super_admin.domain.rules import (
    require_can_create_companies,
    require_can_delete_companies,
)
from app.modules.super_admin.domain.enums import SystemHealthStatus
from app.modules.super_admin.domain.exceptions import SuperAdminPermissionDenied


# ----- Entité SuperAdmin -----


class TestSuperAdminEntity:
    """Entité SuperAdmin (domain/entities.py)."""

    def test_entity_creation_with_required_fields(self):
        """Création avec tous les champs requis."""
        uid = uuid4()
        user_id = uuid4()
        sa = SuperAdmin(
            id=uid,
            user_id=user_id,
            email="admin@plateforme.fr",
            first_name="Super",
            last_name="Admin",
            can_create_companies=True,
            can_delete_companies=False,
            can_view_all_data=True,
            can_impersonate=False,
            is_active=True,
        )
        assert sa.id == uid
        assert sa.user_id == user_id
        assert sa.email == "admin@plateforme.fr"
        assert sa.first_name == "Super"
        assert sa.last_name == "Admin"
        assert sa.can_create_companies is True
        assert sa.can_delete_companies is False
        assert sa.can_view_all_data is True
        assert sa.can_impersonate is False
        assert sa.is_active is True
        assert sa.created_at is None
        assert sa.last_login_at is None
        assert sa.notes is None

    def test_entity_with_optional_fields(self):
        """Création avec champs optionnels."""
        uid = uuid4()
        now = datetime.utcnow()
        sa = SuperAdmin(
            id=uid,
            user_id=uid,
            email="a@b.fr",
            first_name="A",
            last_name="B",
            can_create_companies=True,
            can_delete_companies=True,
            can_view_all_data=True,
            can_impersonate=True,
            is_active=True,
            created_at=now,
            last_login_at=now,
            notes="Note test",
        )
        assert sa.created_at == now
        assert sa.last_login_at == now
        assert sa.notes == "Note test"

    def test_entity_is_mutable(self):
        """L'entité n'est pas frozen : champs modifiables."""
        sa = SuperAdmin(
            id=uuid4(),
            user_id=uuid4(),
            email="x@y.fr",
            first_name="X",
            last_name="Y",
            can_create_companies=True,
            can_delete_companies=False,
            can_view_all_data=True,
            can_impersonate=False,
            is_active=True,
        )
        sa.notes = "Modifié"
        assert sa.notes == "Modifié"


# ----- Value object SuperAdminPermissions -----


class TestSuperAdminPermissions:
    """Value object SuperAdminPermissions (domain/value_objects.py)."""

    def test_permissions_creation(self):
        """Création avec toutes les permissions."""
        perms = SuperAdminPermissions(
            can_create_companies=True,
            can_delete_companies=True,
            can_view_all_data=True,
            can_impersonate=True,
        )
        assert perms.can_create_companies is True
        assert perms.can_delete_companies is True
        assert perms.can_view_all_data is True
        assert perms.can_impersonate is True

    def test_permissions_frozen(self):
        """Le value object est immutable."""
        perms = SuperAdminPermissions(
            can_create_companies=False,
            can_delete_companies=False,
            can_view_all_data=True,
            can_impersonate=False,
        )
        with pytest.raises(FrozenInstanceError):
            perms.can_create_companies = True


# ----- Règles métier -----


class TestRequireCanCreateCompanies:
    """Règle require_can_create_companies (domain/rules.py)."""

    def test_passes_when_permission_true(self):
        """Ne lève pas si can_create_companies=True."""
        sa = SuperAdmin(
            id=uuid4(),
            user_id=uuid4(),
            email="a@b.fr",
            first_name="A",
            last_name="B",
            can_create_companies=True,
            can_delete_companies=False,
            can_view_all_data=True,
            can_impersonate=False,
            is_active=True,
        )
        require_can_create_companies(sa)  # no raise

    def test_raises_when_permission_false(self):
        """Lève SuperAdminPermissionDenied si can_create_companies=False."""
        sa = SuperAdmin(
            id=uuid4(),
            user_id=uuid4(),
            email="a@b.fr",
            first_name="A",
            last_name="B",
            can_create_companies=False,
            can_delete_companies=False,
            can_view_all_data=True,
            can_impersonate=False,
            is_active=True,
        )
        with pytest.raises(SuperAdminPermissionDenied) as exc_info:
            require_can_create_companies(sa)
        assert "créer des entreprises" in str(exc_info.value)


class TestRequireCanDeleteCompanies:
    """Règle require_can_delete_companies (domain/rules.py)."""

    def test_passes_when_permission_true(self):
        """Ne lève pas si can_delete_companies=True."""
        sa = SuperAdmin(
            id=uuid4(),
            user_id=uuid4(),
            email="a@b.fr",
            first_name="A",
            last_name="B",
            can_create_companies=False,
            can_delete_companies=True,
            can_view_all_data=True,
            can_impersonate=False,
            is_active=True,
        )
        require_can_delete_companies(sa)  # no raise

    def test_raises_when_permission_false(self):
        """Lève SuperAdminPermissionDenied si can_delete_companies=False."""
        sa = SuperAdmin(
            id=uuid4(),
            user_id=uuid4(),
            email="a@b.fr",
            first_name="A",
            last_name="B",
            can_create_companies=True,
            can_delete_companies=False,
            can_view_all_data=True,
            can_impersonate=False,
            is_active=True,
        )
        with pytest.raises(SuperAdminPermissionDenied) as exc_info:
            require_can_delete_companies(sa)
        assert "supprimer des entreprises" in str(exc_info.value)


# ----- Enum SystemHealthStatus -----


class TestSystemHealthStatus:
    """Enum SystemHealthStatus (domain/enums.py)."""

    def test_values(self):
        """Valeurs attendues pour GET /system/health."""
        assert SystemHealthStatus.HEALTHY == "healthy"
        assert SystemHealthStatus.DEGRADED == "degraded"
        assert SystemHealthStatus.ERROR == "error"

    def test_str_enum(self):
        """Héritage str, Enum : utilisable en string."""
        s = SystemHealthStatus.HEALTHY
        assert s == "healthy"
        assert isinstance(s, str)


# ----- Exception SuperAdminPermissionDenied -----


class TestSuperAdminPermissionDenied:
    """Exception domaine (domain/exceptions.py)."""

    def test_inherits_exception(self):
        """Hérite de Exception."""
        assert issubclass(SuperAdminPermissionDenied, Exception)

    def test_message_preserved(self):
        """Le message est conservé."""
        exc = SuperAdminPermissionDenied("Message personnalisé")
        assert str(exc) == "Message personnalisé"
