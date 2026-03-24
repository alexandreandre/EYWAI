"""
Tests unitaires des queries du module monthly_inputs (application/queries.py).

Repository et provider catalogue mockés. Pas de DB ni HTTP.
"""
from unittest.mock import patch

import pytest

from app.modules.monthly_inputs.application import queries


class TestListMonthlyInputsByPeriod:
    """Query list_monthly_inputs_by_period."""

    def test_returns_dto_with_items_from_repository(self):
        """list_by_period appelé avec year/month, retourne ListMonthlyInputsResultDto avec items."""
        repo_items = [
            {
                "id": "id-1",
                "employee_id": "emp-1",
                "year": 2025,
                "month": 3,
                "name": "Prime",
                "amount": 100.0,
            },
        ]
        with patch(
            "app.modules.monthly_inputs.application.queries.monthly_inputs_repository"
        ) as repo:
            repo.list_by_period.return_value = repo_items
            result = queries.list_monthly_inputs_by_period(2025, 3)

        assert result.items == repo_items
        repo.list_by_period.assert_called_once_with(2025, 3)

    def test_empty_list_when_no_inputs(self):
        """Aucune saisie pour la période → items vide."""
        with patch(
            "app.modules.monthly_inputs.application.queries.monthly_inputs_repository"
        ) as repo:
            repo.list_by_period.return_value = []
            result = queries.list_monthly_inputs_by_period(2024, 12)

        assert result.items == []
        repo.list_by_period.assert_called_once_with(2024, 12)


class TestListMonthlyInputsByEmployeePeriod:
    """Query list_monthly_inputs_by_employee_period."""

    def test_returns_dto_with_items_for_employee(self):
        """list_by_employee_period appelé avec employee_id, year, month."""
        repo_items = [
            {
                "id": "id-2",
                "employee_id": "emp-abc",
                "year": 2025,
                "month": 6,
                "name": "Acompte",
                "amount": 250.0,
            },
        ]
        with patch(
            "app.modules.monthly_inputs.application.queries.monthly_inputs_repository"
        ) as repo:
            repo.list_by_employee_period.return_value = repo_items
            result = queries.list_monthly_inputs_by_employee_period(
                "emp-abc", 2025, 6
            )

        assert result.items == repo_items
        repo.list_by_employee_period.assert_called_once_with("emp-abc", 2025, 6)

    def test_empty_list_when_no_inputs_for_employee(self):
        """Aucune saisie pour l'employé sur la période → items vide."""
        with patch(
            "app.modules.monthly_inputs.application.queries.monthly_inputs_repository"
        ) as repo:
            repo.list_by_employee_period.return_value = []
            result = queries.list_monthly_inputs_by_employee_period(
                "emp-unknown", 2025, 1
            )

        assert result.items == []


class TestGetPrimesCatalogue:
    """Query get_primes_catalogue."""

    def test_returns_catalogue_from_provider(self):
        """Délègue au primes_catalogue_provider, retourne la liste."""
        catalogue = [
            {"code": "prime_exceptionnelle", "libelle": "Prime exceptionnelle"},
            {"code": "acompte", "libelle": "Acompte"},
        ]
        with patch(
            "app.modules.monthly_inputs.application.queries.primes_catalogue_provider"
        ) as provider:
            provider.get_primes_catalogue.return_value = catalogue
            result = queries.get_primes_catalogue()

        assert result == catalogue
        provider.get_primes_catalogue.assert_called_once()

    def test_returns_empty_list_when_provider_returns_empty(self):
        """Provider retourne [] → liste vide."""
        with patch(
            "app.modules.monthly_inputs.application.queries.primes_catalogue_provider"
        ) as provider:
            provider.get_primes_catalogue.return_value = []
            result = queries.get_primes_catalogue()

        assert result == []