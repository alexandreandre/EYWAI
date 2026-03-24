"""
Tests unitaires des commandes access_control (application/commands.py).

Repositories mockés : require_rh_access, require_rh_access_for_company,
quick_create_role_template.
"""
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.modules.access_control.application import commands
from app.modules.users.schemas.responses import CompanyAccess, User


def _make_user(
    user_id: str = "user-1",
    is_super_admin: bool = False,
    accessible_companies: list | None = None,
) -> User:
    """Fabrique un User pour les tests."""
    if accessible_companies is None:
        accessible_companies = [
            CompanyAccess(
                company_id="company-1",
                company_name="Entreprise 1",
                role="rh",
                is_primary=True,
            ),
        ]
    return User(
        id=user_id,
        email="user@example.com",
        first_name="Test",
        last_name="User",
        is_super_admin=is_super_admin,
        accessible_companies=accessible_companies,
        active_company_id="company-1",
    )


class TestRequireRhAccess:
    """require_rh_access(current_user) — lève 403 si pas d'accès RH."""

    def test_super_admin_does_not_raise(self):
        """Super admin ne lève jamais."""
        user = _make_user(is_super_admin=True, accessible_companies=[])
        commands.require_rh_access(user)  # no raise

    def test_user_with_rh_in_one_company_does_not_raise(self):
        """Utilisateur avec rôle RH dans au moins une entreprise ne lève pas."""
        user = _make_user(accessible_companies=[
            CompanyAccess(company_id="c1", company_name="C1", role="rh", is_primary=True),
        ])
        commands.require_rh_access(user)  # no raise

    def test_user_with_admin_does_not_raise(self):
        """Utilisateur admin a accès RH."""
        user = _make_user(accessible_companies=[
            CompanyAccess(company_id="c1", company_name="C1", role="admin", is_primary=True),
        ])
        commands.require_rh_access(user)  # no raise

    def test_user_with_collaborateur_rh_does_not_raise(self):
        """Collaborateur RH a accès RH."""
        user = _make_user(accessible_companies=[
            CompanyAccess(company_id="c1", company_name="C1", role="collaborateur_rh", is_primary=True),
        ])
        commands.require_rh_access(user)  # no raise

    def test_user_with_only_collaborateur_raises_403(self):
        """Utilisateur uniquement collaborateur (sans RH) → 403."""
        user = _make_user(accessible_companies=[
            CompanyAccess(company_id="c1", company_name="C1", role="collaborateur", is_primary=True),
        ])
        with pytest.raises(HTTPException) as exc_info:
            commands.require_rh_access(user)
        assert exc_info.value.status_code == 403
        assert "Accès RH requis" in str(exc_info.value.detail)

    def test_user_with_no_companies_raises_403(self):
        """Utilisateur sans entreprise → 403."""
        user = _make_user(accessible_companies=[])
        with pytest.raises(HTTPException) as exc_info:
            commands.require_rh_access(user)
        assert exc_info.value.status_code == 403


class TestRequireRhAccessForCompany:
    """require_rh_access_for_company(current_user, company_id)."""

    def test_super_admin_does_not_raise(self):
        """Super admin ne lève jamais."""
        user = _make_user(is_super_admin=True, accessible_companies=[])
        commands.require_rh_access_for_company(user, "any-company")  # no raise

    def test_user_with_rh_in_that_company_does_not_raise(self):
        """Utilisateur RH pour cette entreprise ne lève pas."""
        user = _make_user(accessible_companies=[
            CompanyAccess(company_id="company-1", company_name="C1", role="rh", is_primary=True),
        ])
        commands.require_rh_access_for_company(user, "company-1")  # no raise

    def test_user_without_access_to_company_raises_403(self):
        """Utilisateur sans accès à cette entreprise → 403."""
        user = _make_user(accessible_companies=[
            CompanyAccess(company_id="other-company", company_name="Other", role="rh", is_primary=True),
        ])
        with pytest.raises(HTTPException) as exc_info:
            commands.require_rh_access_for_company(user, "company-1")
        assert exc_info.value.status_code == 403
        assert "Accès RH requis" in str(exc_info.value.detail)

    def test_user_collaborateur_in_company_raises_403(self):
        """Utilisateur collaborateur dans cette entreprise (pas RH) → 403."""
        user = _make_user(accessible_companies=[
            CompanyAccess(company_id="company-1", company_name="C1", role="collaborateur", is_primary=True),
        ])
        with pytest.raises(HTTPException) as exc_info:
            commands.require_rh_access_for_company(user, "company-1")
        assert exc_info.value.status_code == 403


class TestQuickCreateRoleTemplate:
    """quick_create_role_template(...) — crée un template et associe les permissions."""

    @patch("app.modules.access_control.application.commands.role_template_repository")
    def test_creates_template_and_returns_message(self, mock_repo: MagicMock):
        """Crée le template via le repo et retourne message, template_id, name."""
        mock_repo.role_template_name_exists.return_value = False
        mock_repo.create_role_template.return_value = "template-id-123"

        user = _make_user(accessible_companies=[
            CompanyAccess(company_id="company-1", company_name="C1", role="rh", is_primary=True),
        ])

        result = commands.quick_create_role_template(
            current_user=user,
            name="Responsable Paie",
            job_title="Responsable",
            base_role="rh",
            company_id="company-1",
            description="Template test",
            permission_ids=["perm-1", "perm-2"],
        )

        mock_repo.role_template_name_exists.assert_called_once_with("company-1", "Responsable Paie")
        mock_repo.create_role_template.assert_called_once()
        call_kw = mock_repo.create_role_template.call_args[1]
        assert call_kw["company_id"] == "company-1"
        assert call_kw["name"] == "Responsable Paie"
        assert call_kw["job_title"] == "Responsable"
        assert call_kw["base_role"] == "rh"
        assert call_kw["description"] == "Template test"
        assert call_kw["created_by"] == "user-1"

        mock_repo.attach_permissions_to_role_template.assert_called_once_with(
            "template-id-123", ["perm-1", "perm-2"]
        )

        assert result["message"] == "Template créé avec succès"
        assert result["template_id"] == "template-id-123"
        assert result["name"] == "Responsable Paie"

    @patch("app.modules.access_control.application.commands.role_template_repository")
    def test_super_admin_bypasses_rh_check(self, mock_repo: MagicMock):
        """Super admin peut créer sans avoir d'accès RH à l'entreprise."""
        mock_repo.role_template_name_exists.return_value = False
        mock_repo.create_role_template.return_value = "tpl-1"

        user = _make_user(is_super_admin=True, accessible_companies=[])

        result = commands.quick_create_role_template(
            current_user=user,
            name="Template SA",
            job_title="Job",
            base_role="admin",
            company_id="company-x",
        )

        assert result["template_id"] == "tpl-1"
        mock_repo.create_role_template.assert_called_once()

    @patch("app.modules.access_control.application.commands.role_template_repository")
    def test_raises_403_when_no_rh_access_for_company(self, mock_repo: MagicMock):
        """Sans accès RH pour l'entreprise (et pas super_admin) → 403."""
        mock_repo.role_template_name_exists.return_value = False

        user = _make_user(accessible_companies=[
            CompanyAccess(company_id="other", company_name="Other", role="rh", is_primary=True),
        ])

        with pytest.raises(HTTPException) as exc_info:
            commands.quick_create_role_template(
                current_user=user,
                name="Template",
                job_title="Job",
                base_role="rh",
                company_id="company-1",
            )
        assert exc_info.value.status_code == 403
        assert "Accès RH requis" in str(exc_info.value.detail)
        mock_repo.create_role_template.assert_not_called()

    @patch("app.modules.access_control.application.commands.role_template_repository")
    def test_raises_400_when_name_exists(self, mock_repo: MagicMock):
        """Si un template avec ce nom existe déjà pour l'entreprise → 400."""
        mock_repo.role_template_name_exists.return_value = True

        user = _make_user(accessible_companies=[
            CompanyAccess(company_id="company-1", company_name="C1", role="rh", is_primary=True),
        ])

        with pytest.raises(HTTPException) as exc_info:
            commands.quick_create_role_template(
                current_user=user,
                name="Doublon",
                job_title="Job",
                base_role="rh",
                company_id="company-1",
            )
        assert exc_info.value.status_code == 400
        assert "existe déjà" in str(exc_info.value.detail)
        mock_repo.create_role_template.assert_not_called()

    @patch("app.modules.access_control.application.commands.role_template_repository")
    def test_no_permission_ids_does_not_attach(self, mock_repo: MagicMock):
        """Sans permission_ids, attach_permissions n'est pas appelé."""
        mock_repo.role_template_name_exists.return_value = False
        mock_repo.create_role_template.return_value = "tpl-1"

        user = _make_user(accessible_companies=[
            CompanyAccess(company_id="company-1", company_name="C1", role="rh", is_primary=True),
        ])

        commands.quick_create_role_template(
            current_user=user,
            name="Sans perms",
            job_title="Job",
            base_role="collaborateur",
            company_id="company-1",
            permission_ids=None,
        )

        mock_repo.attach_permissions_to_role_template.assert_not_called()
