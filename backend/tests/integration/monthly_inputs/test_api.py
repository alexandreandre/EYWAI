"""
Tests d'intégration HTTP des routes du module monthly_inputs.

Routes : GET/POST/DELETE /api/monthly-inputs, GET/POST/DELETE /api/employees/{id}/monthly-inputs,
GET /api/primes-catalogue. Le routeur n'utilise pas get_current_user (pas d'auth sur ces routes).
Utilise : client (TestClient), mocks sur commands/queries pour éviter la DB réelle.
Pour tests avec DB de test : fournir db_session (conftest) et retirer les patches.

Fixture optionnelle (conftest) si ajout d'auth plus tard :
  monthly_inputs_headers : en-têtes pour un utilisateur avec accès aux saisies mensuelles.
"""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


pytestmark = pytest.mark.integration


# --- GET /api/monthly-inputs ---


class TestListMonthlyInputs:
    """GET /api/monthly-inputs?year=&month= — liste toutes les saisies du mois."""

    def test_list_returns_200_and_list(self, client: TestClient):
        """Retourne 200 et un tableau (vide ou non)."""
        with patch(
            "app.modules.monthly_inputs.api.router.queries.list_monthly_inputs_by_period"
        ) as list_fn:
            list_fn.return_value = type("R", (), {"items": []})()
            list_fn.return_value.items = []
            response = client.get("/api/monthly-inputs?year=2025&month=3")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_list_with_items_returns_data(self, client: TestClient):
        """Quand le module renvoie des items, la réponse les contient."""
        with patch(
            "app.modules.monthly_inputs.api.router.queries.list_monthly_inputs_by_period"
        ) as list_fn:
            list_fn.return_value = type("R", (), {"items": []})()
            list_fn.return_value.items = [
                {
                    "id": "mi-1",
                    "employee_id": "emp-1",
                    "year": 2025,
                    "month": 3,
                    "name": "Prime",
                    "amount": 100.0,
                }
            ]
            response = client.get("/api/monthly-inputs?year=2025&month=3")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "Prime"
        assert data[0]["amount"] == 100.0

    def test_list_missing_params_returns_422(self, client: TestClient):
        """Paramètres year/month manquants → 422."""
        response = client.get("/api/monthly-inputs")
        assert response.status_code == 422


# --- POST /api/monthly-inputs ---


class TestCreateMonthlyInputs:
    """POST /api/monthly-inputs — création en batch."""

    def test_create_batch_returns_201(self, client: TestClient):
        """Body valide → 201 et inserted count."""
        with patch(
            "app.modules.monthly_inputs.api.router.commands.create_monthly_inputs_batch"
        ) as create_fn:
            create_fn.return_value = type("R", (), {"inserted_count": 2})()
            create_fn.return_value.inserted_count = 2
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
        data = response.json()
        assert data.get("status") == "success"
        assert data.get("inserted") == 2

    def test_create_batch_invalid_body_returns_422(self, client: TestClient):
        """Body invalide (manque employee_id ou amount) → 422."""
        response = client.post("/api/monthly-inputs", json=[{"year": 2025, "month": 3}])
        assert response.status_code == 422


# --- DELETE /api/monthly-inputs/{input_id} ---


class TestDeleteMonthlyInput:
    """DELETE /api/monthly-inputs/{input_id}."""

    def test_delete_returns_200(self, client: TestClient):
        """Suppression par id → 200 et status success."""
        with patch(
            "app.modules.monthly_inputs.api.router.commands.delete_monthly_input"
        ):
            response = client.delete("/api/monthly-inputs/input-uuid-123")
        assert response.status_code == 200
        assert response.json().get("status") == "success"


# --- GET /api/employees/{employee_id}/monthly-inputs ---


class TestGetEmployeeMonthlyInputs:
    """GET /api/employees/{employee_id}/monthly-inputs?year=&month=."""

    def test_get_employee_inputs_returns_200(self, client: TestClient):
        """Retourne 200 et une liste."""
        with patch(
            "app.modules.monthly_inputs.api.router.queries.list_monthly_inputs_by_employee_period"
        ) as list_fn:
            list_fn.return_value = type("R", (), {"items": []})()
            list_fn.return_value.items = []
            response = client.get(
                "/api/employees/550e8400-e29b-41d4-a716-446655440000/monthly-inputs?year=2025&month=4"
            )
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_get_employee_inputs_with_data(self, client: TestClient):
        """Réponse contient les saisies de l'employé."""
        with patch(
            "app.modules.monthly_inputs.api.router.queries.list_monthly_inputs_by_employee_period"
        ) as list_fn:
            list_fn.return_value = type("R", (), {"items": []})()
            list_fn.return_value.items = [
                {"id": "mi-2", "name": "Acompte", "amount": 200.0}
            ]
            response = client.get(
                "/api/employees/emp-1/monthly-inputs?year=2025&month=5"
            )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "Acompte"


# --- POST /api/employees/{employee_id}/monthly-inputs ---


class TestCreateEmployeeMonthlyInput:
    """POST /api/employees/{employee_id}/monthly-inputs."""

    def test_create_single_returns_201(self, client: TestClient):
        """Création d'une saisie pour un employé → 201 et inserted_data."""
        with patch(
            "app.modules.monthly_inputs.api.router.commands.create_employee_monthly_input"
        ) as create_fn:
            create_fn.return_value = type("R", (), {"inserted_data": {}})()
            create_fn.return_value.inserted_data = {
                "id": "new-1",
                "employee_id": "emp-1",
                "year": 2025,
                "month": 6,
                "name": "Prime",
                "amount": 150.0,
            }
            response = client.post(
                "/api/employees/emp-1/monthly-inputs",
                json={
                    "year": 2025,
                    "month": 6,
                    "name": "Prime",
                    "amount": 150.0,
                },
            )
        assert response.status_code == 201
        data = response.json()
        assert data.get("status") == "success"
        assert "inserted_data" in data
        assert data["inserted_data"]["name"] == "Prime"

    def test_create_single_invalid_body_returns_422(self, client: TestClient):
        """Body sans year/month/name/amount → 422."""
        response = client.post(
            "/api/employees/emp-1/monthly-inputs",
            json={"name": "Prime"},
        )
        assert response.status_code == 422


# --- DELETE /api/employees/{employee_id}/monthly-inputs/{input_id} ---


class TestDeleteEmployeeMonthlyInput:
    """DELETE /api/employees/{employee_id}/monthly-inputs/{input_id}."""

    def test_delete_employee_input_returns_200(self, client: TestClient):
        """Suppression par employee_id + input_id → 200."""
        with patch(
            "app.modules.monthly_inputs.api.router.commands.delete_employee_monthly_input"
        ):
            response = client.delete("/api/employees/emp-1/monthly-inputs/input-id-456")
        assert response.status_code == 200
        assert response.json().get("status") == "success"


# --- GET /api/primes-catalogue ---


class TestGetPrimesCatalogue:
    """GET /api/primes-catalogue."""

    def test_get_primes_catalogue_returns_200(self, client: TestClient):
        """Retourne 200 et une liste (catalogue de primes)."""
        with patch(
            "app.modules.monthly_inputs.api.router.queries.get_primes_catalogue"
        ) as get_cat:
            get_cat.return_value = [
                {"code": "prime_exceptionnelle", "libelle": "Prime exceptionnelle"},
            ]
            response = client.get("/api/primes-catalogue")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["code"] == "prime_exceptionnelle"

    def test_get_primes_catalogue_empty_returns_200(self, client: TestClient):
        """Catalogue vide → 200 et liste vide."""
        with patch(
            "app.modules.monthly_inputs.api.router.queries.get_primes_catalogue"
        ) as get_cat:
            get_cat.return_value = []
            response = client.get("/api/primes-catalogue")
        assert response.status_code == 200
        assert response.json() == []
