"""
Tests des commandes applicatives du module super_admin (application/commands.py).

Repositories et couche infrastructure mockés ; vérification des règles métier et du délégation.
"""
from unittest.mock import patch

import pytest

from app.modules.super_admin.application import commands
from app.modules.super_admin.application.service import SuperAdminAccessError


# Ligne super_admin pour les tests (can_create_companies=True, can_delete_companies=True)
SUPER_ADMIN_ROW_FULL = {
    "id": "660e8400-e29b-41d4-a716-446655440001",
    "user_id": "660e8400-e29b-41d4-a716-446655440002",
    "email": "super@test.com",
    "first_name": "Super",
    "last_name": "Admin",
    "can_create_companies": True,
    "can_delete_companies": True,
    "can_view_all_data": True,
    "can_impersonate": False,
    "is_active": True,
}

SUPER_ADMIN_ROW_NO_CREATE = {**SUPER_ADMIN_ROW_FULL, "can_create_companies": False}
SUPER_ADMIN_ROW_NO_DELETE = {**SUPER_ADMIN_ROW_FULL, "can_delete_companies": False}


class TestCreateCompanyWithAdmin:
    """Commande create_company_with_admin."""

    def test_delegates_to_infra_when_permission_ok(self):
        """Délègue à l'infra et retourne le résultat si can_create_companies."""
        company_data = {"company_name": "Test Co", "siret": "123"}
        infra_result = {"success": True, "company": {"id": "c1", "company_name": "Test Co"}}
        with patch(
            "app.modules.super_admin.application.commands.infra_commands.create_company_with_admin",
            return_value=infra_result,
        ):
            out = commands.create_company_with_admin(company_data, SUPER_ADMIN_ROW_FULL)
        assert out == infra_result
        assert out["success"] is True
        assert out["company"]["company_name"] == "Test Co"

    def test_raises_super_admin_access_error_when_no_permission(self):
        """Lève SuperAdminAccessError si can_create_companies=False."""
        company_data = {"company_name": "Test Co"}
        with pytest.raises(SuperAdminAccessError) as exc_info:
            commands.create_company_with_admin(company_data, SUPER_ADMIN_ROW_NO_CREATE)
        assert "créer des entreprises" in str(exc_info.value)


class TestUpdateCompany:
    """Commande update_company."""

    def test_delegates_to_infra(self):
        """Délègue à l'infrastructure."""
        with patch(
            "app.modules.super_admin.application.commands.infra_commands.update_company",
            return_value={"success": True, "company": {"id": "c1", "company_name": "Updated"}},
        ) as m:
            out = commands.update_company("c1", {"company_name": "Updated"})
        m.assert_called_once_with("c1", {"company_name": "Updated"})
        assert out["success"] is True
        assert out["company"]["company_name"] == "Updated"


class TestDeleteCompanySoft:
    """Commande delete_company_soft."""

    def test_delegates_when_permission_ok(self):
        """Délègue à l'infra si can_delete_companies."""
        with patch(
            "app.modules.super_admin.application.commands.infra_commands.delete_company_soft",
            return_value={"success": True, "message": "Entreprise désactivée"},
        ) as m:
            out = commands.delete_company_soft("c1", SUPER_ADMIN_ROW_FULL)
        m.assert_called_once_with("c1")
        assert out["message"] == "Entreprise désactivée"

    def test_raises_when_no_delete_permission(self):
        """Lève SuperAdminAccessError si can_delete_companies=False."""
        with pytest.raises(SuperAdminAccessError) as exc_info:
            commands.delete_company_soft("c1", SUPER_ADMIN_ROW_NO_DELETE)
        assert "supprimer des entreprises" in str(exc_info.value)


class TestDeleteCompanyPermanent:
    """Commande delete_company_permanent."""

    def test_delegates_when_permission_ok(self):
        """Délègue à l'infra si can_delete_companies."""
        with patch(
            "app.modules.super_admin.application.commands.infra_commands.delete_company_permanent",
            return_value={"success": True, "message": "Supprimé", "deleted_company": {"id": "c1"}},
        ) as m:
            out = commands.delete_company_permanent("c1", SUPER_ADMIN_ROW_FULL)
        m.assert_called_once_with("c1")
        assert out["success"] is True

    def test_raises_when_no_delete_permission(self):
        """Lève SuperAdminAccessError si can_delete_companies=False."""
        with pytest.raises(SuperAdminAccessError):
            commands.delete_company_permanent("c1", SUPER_ADMIN_ROW_NO_DELETE)


class TestCreateCompanyUser:
    """Commande create_company_user."""

    def test_delegates_to_infra(self):
        """Délègue à l'infrastructure."""
        user_data = {"email": "u@co.fr", "password": "secret", "first_name": "U", "last_name": "N", "role": "admin"}
        with patch(
            "app.modules.super_admin.application.commands.infra_commands.create_company_user",
            return_value={"success": True, "user": {"id": "u1", "email": "u@co.fr"}},
        ) as m:
            out = commands.create_company_user("c1", user_data)
        m.assert_called_once_with("c1", user_data)
        assert out["user"]["email"] == "u@co.fr"


class TestUpdateCompanyUser:
    """Commande update_company_user."""

    def test_delegates_to_infra(self):
        """Délègue à l'infrastructure."""
        with patch(
            "app.modules.super_admin.application.commands.infra_commands.update_company_user",
            return_value={"success": True, "message": "Utilisateur mis à jour avec succès"},
        ) as m:
            out = commands.update_company_user("c1", "u1", {"first_name": "New"})
        m.assert_called_once_with("c1", "u1", {"first_name": "New"})
        assert out["success"] is True


class TestDeleteCompanyUser:
    """Commande delete_company_user."""

    def test_delegates_to_infra(self):
        """Délègue à l'infrastructure."""
        with patch(
            "app.modules.super_admin.application.commands.infra_commands.delete_company_user",
            return_value={"success": True, "message": "Accès supprimé"},
        ) as m:
            out = commands.delete_company_user("c1", "u1")
        m.assert_called_once_with("c1", "u1")
        assert out["message"] == "Accès supprimé"
