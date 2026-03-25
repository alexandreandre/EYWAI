"""
Tests unitaires des queries du module repos_compensateur (application/queries.py).

Repository (infrastructure get_jours_by_employee_year) mocké. Pas de DB ni HTTP.
"""

from unittest.mock import patch

from app.modules.repos_compensateur.application import queries


class TestGetCreditsJoursByEmployeeYear:
    """Query get_credits_jours_by_employee_year."""

    def test_delegates_to_infrastructure_and_returns_dict(self):
        """Délègue à get_jours_by_employee_year et retourne le dict employee_id -> jours."""
        with patch(
            "app.modules.repos_compensateur.application.queries.get_jours_by_employee_year",
            return_value={"emp-1": 5.0, "emp-2": 3.5},
        ) as get_jours:
            result = queries.get_credits_jours_by_employee_year(
                employee_ids=["emp-1", "emp-2"],
                year=2025,
            )
            assert result == {"emp-1": 5.0, "emp-2": 3.5}
            get_jours.assert_called_once_with(["emp-1", "emp-2"], 2025)

    def test_empty_list_returns_empty_dict(self):
        """employee_ids vide → dict vide (infrastructure peut retourner {})."""
        with patch(
            "app.modules.repos_compensateur.application.queries.get_jours_by_employee_year",
            return_value={},
        ) as get_jours:
            result = queries.get_credits_jours_by_employee_year(
                employee_ids=[],
                year=2025,
            )
            assert result == {}
            get_jours.assert_called_once_with([], 2025)

    def test_single_employee(self):
        """Un seul employé → dict à une clé."""
        with patch(
            "app.modules.repos_compensateur.application.queries.get_jours_by_employee_year",
            return_value={"emp-1": 10.0},
        ):
            result = queries.get_credits_jours_by_employee_year(
                employee_ids=["emp-1"],
                year=2024,
            )
            assert result == {"emp-1": 10.0}

    def test_employee_with_zero_jours(self):
        """Employé sans crédits → 0.0 dans le dict (utilisable pour soldes absences)."""
        with patch(
            "app.modules.repos_compensateur.application.queries.get_jours_by_employee_year",
            return_value={"emp-1": 0.0},
        ):
            result = queries.get_credits_jours_by_employee_year(
                employee_ids=["emp-1"],
                year=2025,
            )
            assert result["emp-1"] == 0.0
