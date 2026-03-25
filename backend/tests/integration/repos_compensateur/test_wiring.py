"""
Tests de câblage (wiring) du module repos_compensateur : injection des dépendances et flux bout en bout.

Vérifie que la route API appelle bien la commande applicative et que le module est correctement monté.
"""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app


pytestmark = pytest.mark.integration

# Utilisateur de test avec active_company_id (ReposCompensateurUserContext)
_USER = type("User", (), {"active_company_id": "comp-wiring-test"})()


def _get_current_user():
    return _USER


class TestReposCompensateurRouterMounted:
    """Vérification que le router repos-compensateur est monté et répond."""

    def test_post_calculer_credits_route_exists(self, client: TestClient):
        """POST /api/repos-compensateur/calculer-credits existe et exige l'auth."""
        response = client.post(
            "/api/repos-compensateur/calculer-credits",
            params={"year": 2025, "month": 6},
        )
        # Sans auth → 401 (route protégée)
        assert response.status_code == 401

    def test_post_calculer_credits_calls_command_with_correct_params(
        self, client: TestClient
    ):
        """POST avec auth appelle calculer_credits_repos_command avec year, month, target_company_id."""
        from app.modules.repos_compensateur.api import dependencies

        app.dependency_overrides[dependencies.get_current_user] = _get_current_user
        try:
            with patch(
                "app.modules.repos_compensateur.api.router.calculer_credits_repos_command"
            ) as cmd:
                cmd.return_value = type(
                    "Result",
                    (),
                    {
                        "company_id": "comp-wiring-test",
                        "year": 2025,
                        "month": 6,
                        "employees_processed": 2,
                        "credits_created": 1,
                    },
                )()
                response = client.post(
                    "/api/repos-compensateur/calculer-credits",
                    params={"year": 2025, "month": 6},
                )
                assert response.status_code == 200
                cmd.assert_called_once_with(
                    year=2025,
                    month=6,
                    target_company_id="comp-wiring-test",
                )
        finally:
            app.dependency_overrides.pop(dependencies.get_current_user, None)


class TestReposCompensateurCommandsQueriesWiring:
    """Vérification que commands et queries utilisent bien le service / l'infrastructure."""

    def test_calculer_credits_repos_command_uses_service(self):
        """calculer_credits_repos_command délègue au service calculer_credits_repos."""
        from app.modules.repos_compensateur.application import commands

        with patch(
            "app.modules.repos_compensateur.application.commands.calculer_credits_repos"
        ) as calc:
            from app.modules.repos_compensateur.application.dto import (
                CalculerCreditsResult,
            )

            calc.return_value = CalculerCreditsResult(
                company_id="c1",
                year=2025,
                month=6,
                employees_processed=5,
                credits_created=2,
            )
            result = commands.calculer_credits_repos_command(
                year=2025,
                month=6,
                target_company_id="c1",
            )
            assert result.credits_created == 2
            calc.assert_called_once_with(
                year=2025,
                month=6,
                target_company_id="c1",
            )

    def test_get_credits_jours_by_employee_year_uses_infrastructure(self):
        """get_credits_jours_by_employee_year (query) délègue à get_jours_by_employee_year."""
        from app.modules.repos_compensateur.application import queries

        with patch(
            "app.modules.repos_compensateur.application.queries.get_jours_by_employee_year",
            return_value={"emp-1": 5.0},
        ) as get_jours:
            result = queries.get_credits_jours_by_employee_year(
                employee_ids=["emp-1"],
                year=2025,
            )
            assert result == {"emp-1": 5.0}
            get_jours.assert_called_once_with(["emp-1"], 2025)
