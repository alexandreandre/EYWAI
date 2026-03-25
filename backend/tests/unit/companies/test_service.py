"""
Tests unitaires du service applicatif companies (application/service.py).

Dépendances mockées : get_company_id_from_profile, pas d'accès DB.
"""

from unittest.mock import MagicMock, patch


from app.modules.companies.application import service


QUERIES_INFRA = "app.modules.companies.infrastructure.queries"


class TestResolveCompanyIdForUser:
    """resolve_company_id_for_user : contexte settings (entreprise active)."""

    def test_returns_active_company_id_when_set(self):
        """Retourne active_company_id si renseigné."""
        user = MagicMock()
        user.active_company_id = "company-active"
        user.accessible_companies = []

        result = service.resolve_company_id_for_user(user)
        assert result == "company-active"

    def test_returns_first_accessible_company_when_no_active(self):
        """Retourne company_id du premier accessible_companies si active_company_id vide."""
        user = MagicMock()
        user.active_company_id = None
        acc = MagicMock()
        acc.company_id = "first-company-id"
        user.accessible_companies = [acc]

        result = service.resolve_company_id_for_user(user)
        assert result == "first-company-id"

    def test_returns_none_when_no_company_context(self):
        """Retourne None si pas d'active_company_id ni accessible_companies."""
        user = MagicMock()
        user.active_company_id = None
        user.accessible_companies = []

        result = service.resolve_company_id_for_user(user)
        assert result is None

    def test_returns_none_when_accessible_companies_none(self):
        """Gère accessible_companies = None (fallback comme [])."""
        user = MagicMock()
        user.active_company_id = None
        user.accessible_companies = None

        result = service.resolve_company_id_for_user(user)
        assert result is None


class TestResolveCompanyIdForDetails:
    """resolve_company_id_for_details : company_id depuis profil (profiles.company_id)."""

    def test_returns_company_id_from_profile(self):
        """Délègue à get_company_id_from_profile et retourne le résultat."""
        with patch(
            f"{QUERIES_INFRA}.get_company_id_from_profile",
            return_value="profile-company-id",
        ) as get_profile:
            user = MagicMock()
            user.id = "user-123"
            result = service.resolve_company_id_for_details(user)

            get_profile.assert_called_once_with("user-123")
            assert result == "profile-company-id"

    def test_returns_none_when_profile_has_no_company(self):
        """Retourne None si get_company_id_from_profile retourne None."""
        with patch(
            f"{QUERIES_INFRA}.get_company_id_from_profile",
            return_value=None,
        ):
            user = MagicMock()
            user.id = "user-456"
            result = service.resolve_company_id_for_details(user)
            assert result is None
