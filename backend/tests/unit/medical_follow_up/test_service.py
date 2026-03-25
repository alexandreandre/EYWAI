"""
Tests unitaires du service medical_follow_up (application/service.py).

Dépendances (repository, provider) mockées ; pas de DB ni HTTP.
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.modules.medical_follow_up.application import service


class TestResolveCompanyIdForMedical:
    """resolve_company_id_for_medical."""

    def test_returns_active_company_id_when_set(self):
        """Si active_company_id est renseigné, le retourne."""
        user = MagicMock()
        user.active_company_id = "co-1"
        user.accessible_companies = []
        assert service.resolve_company_id_for_medical(user) == "co-1"

    def test_returns_first_accessible_company_when_no_active(self):
        """Si pas d'active_company_id, utilise accessible_companies[0].company_id."""
        user = MagicMock()
        user.active_company_id = None
        acc = MagicMock()
        acc.company_id = "co-2"
        user.accessible_companies = [acc]
        assert service.resolve_company_id_for_medical(user) == "co-2"

    def test_returns_none_when_no_company(self):
        """Pas d'entreprise active ni accessible → None."""
        user = MagicMock()
        user.active_company_id = None
        user.accessible_companies = []
        assert service.resolve_company_id_for_medical(user) is None

    def test_returns_none_when_accessible_companies_none(self):
        """accessible_companies à None → None."""
        user = MagicMock()
        user.active_company_id = None
        user.accessible_companies = None
        assert service.resolve_company_id_for_medical(user) is None


@patch("app.modules.medical_follow_up.application.service.get_settings_provider")
class TestGetCompanyMedicalSetting:
    """get_company_medical_setting."""

    def test_returns_true_when_provider_enabled(self, mock_get_provider):
        """Provider is_enabled(company_id) True → True."""
        provider = MagicMock()
        provider.is_enabled.return_value = True
        mock_get_provider.return_value = provider
        assert service.get_company_medical_setting("co-1") is True
        provider.is_enabled.assert_called_once_with("co-1")

    def test_returns_false_when_provider_disabled(self, mock_get_provider):
        """Provider is_enabled(company_id) False → False."""
        provider = MagicMock()
        provider.is_enabled.return_value = False
        mock_get_provider.return_value = provider
        assert service.get_company_medical_setting("co-1") is False


class TestEnsureModuleEnabled:
    """ensure_module_enabled."""

    @patch(
        "app.modules.medical_follow_up.application.service.get_company_medical_setting"
    )
    @patch(
        "app.modules.medical_follow_up.application.service.resolve_company_id_for_medical"
    )
    def test_raises_400_when_no_company(self, mock_resolve, mock_setting):
        """Pas d'entreprise active → HTTPException 400."""
        mock_resolve.return_value = None
        with pytest.raises(HTTPException) as exc_info:
            service.ensure_module_enabled(MagicMock())
        assert exc_info.value.status_code == 400
        assert "entreprise" in exc_info.value.detail.lower()
        mock_setting.assert_not_called()

    @patch(
        "app.modules.medical_follow_up.application.service.get_company_medical_setting"
    )
    @patch(
        "app.modules.medical_follow_up.application.service.resolve_company_id_for_medical"
    )
    def test_raises_403_when_module_disabled(self, mock_resolve, mock_setting):
        """Module désactivé pour l'entreprise → HTTPException 403."""
        mock_resolve.return_value = "co-1"
        mock_setting.return_value = False
        with pytest.raises(HTTPException) as exc_info:
            service.ensure_module_enabled(MagicMock())
        assert exc_info.value.status_code == 403
        mock_setting.assert_called_once_with("co-1")

    @patch(
        "app.modules.medical_follow_up.application.service.get_company_medical_setting"
    )
    @patch(
        "app.modules.medical_follow_up.application.service.resolve_company_id_for_medical"
    )
    def test_returns_company_id_when_ok(self, mock_resolve, mock_setting):
        """Entreprise active et module activé → retourne company_id."""
        mock_resolve.return_value = "co-1"
        mock_setting.return_value = True
        result = service.ensure_module_enabled(MagicMock())
        assert result == "co-1"


class TestEnsureRhAccess:
    """ensure_rh_access."""

    def test_raises_403_when_no_rh_access(self):
        """has_rh_access_in_company(company_id) False → HTTPException 403."""
        user = MagicMock()
        user.has_rh_access_in_company = MagicMock(return_value=False)
        with pytest.raises(HTTPException) as exc_info:
            service.ensure_rh_access(user, "co-1")
        assert exc_info.value.status_code == 403
        assert "Accès" in exc_info.value.detail or "autorisé" in exc_info.value.detail
        user.has_rh_access_in_company.assert_called_once_with("co-1")

    def test_does_not_raise_when_rh_access(self):
        """has_rh_access_in_company(company_id) True → ne lève pas."""
        user = MagicMock()
        user.has_rh_access_in_company = MagicMock(return_value=True)
        service.ensure_rh_access(user, "co-1")
        user.has_rh_access_in_company.assert_called_once_with("co-1")

    def test_uses_getattr_when_no_has_rh_access(self):
        """User sans attribut has_rh_access_in_company → getattr défaut False → 403."""

        class UserNoRh:
            pass

        user = UserNoRh()
        with pytest.raises(HTTPException) as exc_info:
            service.ensure_rh_access(user, "co-1")
        assert exc_info.value.status_code == 403
