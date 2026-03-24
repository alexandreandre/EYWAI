"""
Tests d'intégration HTTP des routes du module repos_compensateur.

Route : POST /api/repos-compensateur/calculer-credits (query params: year, month, company_id optionnel).
Utilise : client (TestClient), dependency_overrides pour get_current_user (contexte avec active_company_id),
et patch de calculer_credits_repos_command pour éviter la DB réelle.

Fixture optionnelle (conftest.py) : repos_compensateur_headers
  En-têtes pour un utilisateur avec active_company_id et droits RH.
  Format : {"Authorization": "Bearer <jwt>", "X-Active-Company": "<company_id>"}.
  Si non définie, les tests utilisent dependency_overrides pour injecter un utilisateur de test.
"""
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app


pytestmark = pytest.mark.integration

# Contexte minimal pour les routes repos_compensateur (ReposCompensateurUserContext)
_USER_WITH_COMPANY = type("User", (), {"active_company_id": "comp-test-123"})()


def _override_get_current_user():
    """Retourne un utilisateur de test avec active_company_id."""
    return _USER_WITH_COMPANY


class TestCalculerCreditsReposUnauthenticated:
    """POST /api/repos-compensateur/calculer-credits sans auth."""

    def test_without_token_returns_401(self, client: TestClient):
        """Sans token → 401."""
        response = client.post(
            "/api/repos-compensateur/calculer-credits",
            params={"year": 2025, "month": 6},
        )
        assert response.status_code == 401


class TestCalculerCreditsReposValidation:
    """Validation des paramètres et contexte company."""

    def test_missing_company_id_and_no_active_company_returns_400(
        self, client: TestClient
    ):
        """Sans company_id en query et sans active_company_id dans le user → 400."""
        user_no_company = type("User", (), {"active_company_id": None})()
        from app.modules.repos_compensateur.api import dependencies

        app.dependency_overrides[dependencies.get_current_user] = (
            lambda: user_no_company
        )
        try:
            response = client.post(
                "/api/repos-compensateur/calculer-credits",
                params={"year": 2025, "month": 6},
            )
            assert response.status_code == 400
            data = response.json()
            assert "detail" in data
            assert "company_id" in data["detail"].lower() or "requis" in data["detail"].lower()
        finally:
            app.dependency_overrides.pop(dependencies.get_current_user, None)

    def test_invalid_year_returns_422(self, client: TestClient):
        """year hors plage (ex. 2019 ou 2031) → 422."""
        from app.modules.repos_compensateur.api import dependencies

        app.dependency_overrides[dependencies.get_current_user] = (
            _override_get_current_user
        )
        try:
            response = client.post(
                "/api/repos-compensateur/calculer-credits",
                params={"year": 2019, "month": 6, "company_id": "comp-1"},
            )
            assert response.status_code == 422
        finally:
            app.dependency_overrides.pop(dependencies.get_current_user, None)

    def test_invalid_month_returns_422(self, client: TestClient):
        """month hors 1-12 → 422."""
        from app.modules.repos_compensateur.api import dependencies

        app.dependency_overrides[dependencies.get_current_user] = (
            _override_get_current_user
        )
        try:
            response = client.post(
                "/api/repos-compensateur/calculer-credits",
                params={"year": 2025, "month": 0, "company_id": "comp-1"},
            )
            assert response.status_code == 422
        finally:
            app.dependency_overrides.pop(dependencies.get_current_user, None)


class TestCalculerCreditsReposSuccess:
    """POST /api/repos-compensateur/calculer-credits avec auth et params valides."""

    def test_with_company_id_in_query_returns_200_and_response_model(
        self, client: TestClient
    ):
        """company_id en query → 200 et CalculerCreditsResponse."""
        from app.modules.repos_compensateur.api import dependencies

        app.dependency_overrides[dependencies.get_current_user] = (
            _override_get_current_user
        )
        try:
            with patch(
                "app.modules.repos_compensateur.api.router.calculer_credits_repos_command"
            ) as cmd:
                cmd.return_value = type(
                    "Result",
                    (),
                    {
                        "company_id": "comp-1",
                        "year": 2025,
                        "month": 6,
                        "employees_processed": 10,
                        "credits_created": 4,
                    },
                )()
                response = client.post(
                    "/api/repos-compensateur/calculer-credits",
                    params={"year": 2025, "month": 6, "company_id": "comp-1"},
                )
                assert response.status_code == 200
                data = response.json()
                assert data["company_id"] == "comp-1"
                assert data["year"] == 2025
                assert data["month"] == 6
                assert data["employees_processed"] == 10
                assert data["credits_created"] == 4
                cmd.assert_called_once_with(
                    year=2025,
                    month=6,
                    target_company_id="comp-1",
                )
        finally:
            app.dependency_overrides.pop(dependencies.get_current_user, None)

    def test_with_active_company_id_from_user_returns_200(self, client: TestClient):
        """Sans company_id en query, utilise active_company_id du user → 200."""
        from app.modules.repos_compensateur.api import dependencies

        app.dependency_overrides[dependencies.get_current_user] = (
            _override_get_current_user
        )
        try:
            with patch(
                "app.modules.repos_compensateur.api.router.calculer_credits_repos_command"
            ) as cmd:
                cmd.return_value = type(
                    "Result",
                    (),
                    {
                        "company_id": "comp-test-123",
                        "year": 2025,
                        "month": 1,
                        "employees_processed": 0,
                        "credits_created": 0,
                    },
                )()
                response = client.post(
                    "/api/repos-compensateur/calculer-credits",
                    params={"year": 2025, "month": 1},
                )
                assert response.status_code == 200
                data = response.json()
                assert data["company_id"] == "comp-test-123"
                cmd.assert_called_once_with(
                    year=2025,
                    month=1,
                    target_company_id="comp-test-123",
                )
        finally:
            app.dependency_overrides.pop(dependencies.get_current_user, None)


class TestCalculerCreditsReposErrorHandling:
    """Gestion des erreurs (500 si la commande lève)."""

    def test_command_raises_returns_500(self, client: TestClient):
        """Si la commande lève une exception → 500."""
        from app.modules.repos_compensateur.api import dependencies

        app.dependency_overrides[dependencies.get_current_user] = (
            _override_get_current_user
        )
        try:
            with patch(
                "app.modules.repos_compensateur.api.router.calculer_credits_repos_command",
                side_effect=RuntimeError("DB error"),
            ):
                response = client.post(
                    "/api/repos-compensateur/calculer-credits",
                    params={"year": 2025, "month": 6, "company_id": "comp-1"},
                )
                assert response.status_code == 500
                data = response.json()
                assert "detail" in data
        finally:
            app.dependency_overrides.pop(dependencies.get_current_user, None)
