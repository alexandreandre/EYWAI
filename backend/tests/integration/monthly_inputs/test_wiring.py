"""
Tests de câblage (wiring) du module monthly_inputs.

Vérifient que l'injection des dépendances et le flux de bout en bout
(router -> application commands/queries -> repository / provider) fonctionnent.
"""
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


pytestmark = pytest.mark.integration


class TestMonthlyInputsWiring:
    """Flux complet : routes -> commands/queries -> repository."""

    def test_list_monthly_inputs_flow_uses_queries(self, client: TestClient):
        """GET /api/monthly-inputs : le router appelle queries.list_monthly_inputs_by_period."""
        with patch(
            "app.modules.monthly_inputs.api.router.queries.list_monthly_inputs_by_period"
        ) as list_fn:
            list_fn.return_value = type("R", (), {"items": []})()
            list_fn.return_value.items = [
                {
                    "id": "wiring-1",
                    "employee_id": "emp-1",
                    "year": 2025,
                    "month": 3,
                    "name": "Prime wiring",
                    "amount": 99.0,
                }
            ]
            response = client.get("/api/monthly-inputs?year=2025&month=3")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "Prime wiring"
        list_fn.assert_called_once_with(2025, 3)

    def test_create_batch_flow_uses_commands(self, client: TestClient):
        """POST /api/monthly-inputs : router -> commands.create_monthly_inputs_batch -> repo.insert_batch."""
        with patch(
            "app.modules.monthly_inputs.application.commands.monthly_inputs_repository"
        ) as repo:
            repo.insert_batch.return_value = [
                {"id": "new-1", "employee_id": "550e8400-e29b-41d4-a716-446655440000", "year": 2025, "month": 3, "name": "Prime", "amount": 100.0},
            ]
            response = client.post(
                "/api/monthly-inputs",
                json=[
                    {
                        "employee_id": "550e8400-e29b-41d4-a716-446655440000",
                        "year": 2025,
                        "month": 3,
                        "name": "Prime",
                        "amount": 100.0,
                    },
                ],
            )

        assert response.status_code == 201
        body = response.json()
        assert body["status"] == "success"
        assert body["inserted"] == 1
        repo.insert_batch.assert_called_once()
        call_rows = repo.insert_batch.call_args[0][0]
        assert len(call_rows) == 1
        assert call_rows[0]["name"] == "Prime"

    def test_delete_flow_uses_commands(self, client: TestClient):
        """DELETE /api/monthly-inputs/{id} : router -> commands.delete_monthly_input -> repo.delete_by_id."""
        with patch(
            "app.modules.monthly_inputs.application.commands.monthly_inputs_repository"
        ) as repo:
            response = client.delete("/api/monthly-inputs/wiring-delete-id")

        assert response.status_code == 200
        repo.delete_by_id.assert_called_once_with("wiring-delete-id")

    def test_get_employee_monthly_inputs_flow_uses_queries(self, client: TestClient):
        """GET /api/employees/{id}/monthly-inputs : queries.list_monthly_inputs_by_employee_period."""
        with patch(
            "app.modules.monthly_inputs.api.router.queries.list_monthly_inputs_by_employee_period"
        ) as list_fn:
            list_fn.return_value = type("R", (), {"items": []})()
            list_fn.return_value.items = []
            response = client.get(
                "/api/employees/emp-wiring/monthly-inputs?year=2025&month=6"
            )

        assert response.status_code == 200
        list_fn.assert_called_once_with("emp-wiring", 2025, 6)

    def test_create_employee_monthly_input_flow_uses_commands(self, client: TestClient):
        """POST /api/employees/{id}/monthly-inputs : commands.create_employee_monthly_input -> repo.insert_one."""
        with patch(
            "app.modules.monthly_inputs.application.commands.monthly_inputs_repository"
        ) as repo:
            repo.insert_one.return_value = {
                "id": "new-emp-1",
                "employee_id": "emp-wiring",
                "year": 2025,
                "month": 7,
                "name": "Acompte",
                "amount": 200.0,
            }
            response = client.post(
                "/api/employees/emp-wiring/monthly-inputs",
                json={
                    "year": 2025,
                    "month": 7,
                    "name": "Acompte",
                    "amount": 200.0,
                },
            )

        assert response.status_code == 201
        body = response.json()
        assert body["inserted_data"]["name"] == "Acompte"
        repo.insert_one.assert_called_once()
        call_row = repo.insert_one.call_args[0][0]
        assert call_row["employee_id"] == "emp-wiring"
        assert call_row["year"] == 2025
        assert call_row["month"] == 7

    def test_delete_employee_monthly_input_flow_uses_commands(self, client: TestClient):
        """DELETE /api/employees/{id}/monthly-inputs/{input_id} : commands.delete_employee_monthly_input."""
        with patch(
            "app.modules.monthly_inputs.application.commands.monthly_inputs_repository"
        ) as repo:
            response = client.delete(
                "/api/employees/emp-wiring/monthly-inputs/input-wiring-1"
            )

        assert response.status_code == 200
        repo.delete_by_id_and_employee.assert_called_once_with(
            "input-wiring-1", "emp-wiring"
        )

    def test_primes_catalogue_flow_uses_queries(self, client: TestClient):
        """GET /api/primes-catalogue : queries.get_primes_catalogue -> provider.get_primes_catalogue."""
        with patch(
            "app.modules.monthly_inputs.api.router.queries.get_primes_catalogue"
        ) as get_cat:
            get_cat.return_value = [
                {"code": "prime_wiring", "libelle": "Prime wiring test"},
            ]
            response = client.get("/api/primes-catalogue")

        assert response.status_code == 200
        data = response.json()
        assert data[0]["code"] == "prime_wiring"
        get_cat.assert_called_once()
