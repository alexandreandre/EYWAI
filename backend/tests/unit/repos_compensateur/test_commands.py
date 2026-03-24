"""
Tests unitaires des commandes du module repos_compensateur (application/commands.py).

Repositories et providers (infrastructure) mockés. Pas de DB ni HTTP.
"""
from unittest.mock import patch

import pytest

from app.modules.repos_compensateur.application import commands
from app.modules.repos_compensateur.application.dto import CalculerCreditsResult


class TestRecalculerCreditsReposEmployeCommand:
    """Commande recalculer_credits_repos_employe_command."""

    def test_returns_number_of_credits_upserted(self):
        """Délègue au service et retourne le nombre de lignes upsertées."""
        with patch(
            "app.modules.repos_compensateur.application.commands.recalculer_credits_repos_employe",
            return_value=12,
        ) as recalc:
            result = commands.recalculer_credits_repos_employe_command(
                employee_id="emp-1",
                company_id="comp-1",
                year=2025,
            )
            assert result == 12
            recalc.assert_called_once_with("emp-1", "comp-1", 2025)

    def test_returns_zero_when_service_returns_zero(self):
        """Si le service retourne 0 (ex. erreur ou aucun crédit), la commande retourne 0."""
        with patch(
            "app.modules.repos_compensateur.application.commands.recalculer_credits_repos_employe",
            return_value=0,
        ):
            result = commands.recalculer_credits_repos_employe_command(
                employee_id="emp-2",
                company_id="comp-2",
                year=2024,
            )
            assert result == 0


class TestCalculerCreditsReposCommand:
    """Commande calculer_credits_repos_command."""

    def test_delegates_to_service_and_returns_result(self):
        """Délègue au service et retourne CalculerCreditsResult."""
        expected = CalculerCreditsResult(
            company_id="comp-1",
            year=2025,
            month=6,
            employees_processed=5,
            credits_created=3,
        )
        with patch(
            "app.modules.repos_compensateur.application.commands.calculer_credits_repos",
            return_value=expected,
        ) as calc:
            result = commands.calculer_credits_repos_command(
                year=2025,
                month=6,
                target_company_id="comp-1",
            )
            assert result == expected
            assert result.company_id == "comp-1"
            assert result.year == 2025
            assert result.month == 6
            assert result.employees_processed == 5
            assert result.credits_created == 3
            calc.assert_called_once_with(
                year=2025,
                month=6,
                target_company_id="comp-1",
            )

    def test_zero_employees_processed_when_none_in_company(self):
        """Si l'entreprise n'a aucun employé, employees_processed=0, credits_created=0."""
        expected = CalculerCreditsResult(
            company_id="comp-vide",
            year=2025,
            month=1,
            employees_processed=0,
            credits_created=0,
        )
        with patch(
            "app.modules.repos_compensateur.application.commands.calculer_credits_repos",
            return_value=expected,
        ):
            result = commands.calculer_credits_repos_command(
                year=2025,
                month=1,
                target_company_id="comp-vide",
            )
            assert result.employees_processed == 0
            assert result.credits_created == 0
