"""
Tests d'intégration HTTP des routes du module participation (Participation & Intéressement).

Préfixe des routes : /api/participation.
Utilise : client (TestClient). Pour les tests authentifiés, dependency_overrides pour
get_current_user (depuis app.modules.participation.api.dependencies) et patch du service
ou des commands/queries pour éviter la DB réelle.
Fixture optionnelle : participation_headers (conftest) pour tests E2E avec token réel.
"""

from datetime import datetime
from uuid import uuid4
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app


pytestmark = pytest.mark.integration

TEST_COMPANY_ID = "550e8400-e29b-41d4-a716-446655440000"
TEST_USER_ID = "660e8400-e29b-41d4-a716-446655440001"


def _make_user_with_company():
    """Utilisateur de test avec active_company_id (contrat ParticipationUserContext)."""
    user = MagicMock()
    user.id = TEST_USER_ID
    user.active_company_id = TEST_COMPANY_ID
    return user


def _make_user_without_company():
    """Utilisateur sans entreprise active → 403 sur les routes qui requièrent company_id."""
    user = MagicMock()
    user.id = TEST_USER_ID
    user.active_company_id = None
    return user


class TestParticipationUnauthenticated:
    """Sans token : toutes les routes protégées renvoient 401."""

    def test_get_employee_data_returns_401_without_auth(self, client: TestClient):
        """GET /api/participation/employee-data/{year} sans auth → 401."""
        response = client.get("/api/participation/employee-data/2024")
        assert response.status_code == 401

    def test_post_simulations_returns_401_without_auth(self, client: TestClient):
        """POST /api/participation/simulations sans auth → 401."""
        response = client.post(
            "/api/participation/simulations",
            json={
                "year": 2024,
                "simulation_name": "Test",
                "benefice_net": 0,
                "capitaux_propres": 0,
                "salaires_bruts": 0,
                "valeur_ajoutee": 0,
                "participation_mode": "uniforme",
                "results_data": {},
            },
        )
        assert response.status_code == 401

    def test_get_simulations_returns_401_without_auth(self, client: TestClient):
        """GET /api/participation/simulations sans auth → 401."""
        response = client.get("/api/participation/simulations")
        assert response.status_code == 401

    def test_get_simulation_by_id_returns_401_without_auth(self, client: TestClient):
        """GET /api/participation/simulations/{id} sans auth → 401."""
        response = client.get("/api/participation/simulations/sim-123")
        assert response.status_code == 401

    def test_delete_simulation_returns_401_without_auth(self, client: TestClient):
        """DELETE /api/participation/simulations/{id} sans auth → 401."""
        response = client.delete("/api/participation/simulations/sim-123")
        assert response.status_code == 401


class TestParticipationWithUserNoCompany:
    """Utilisateur authentifié sans active_company_id → 403."""

    @pytest.fixture
    def client_no_company(self, client: TestClient):
        from app.modules.participation.api.dependencies import get_current_user

        app.dependency_overrides[get_current_user] = lambda: (
            _make_user_without_company()
        )
        try:
            yield client
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    def test_get_employee_data_returns_403(self, client_no_company: TestClient):
        """GET /api/participation/employee-data/{year} sans company → 403."""
        response = client_no_company.get("/api/participation/employee-data/2024")
        assert response.status_code == 403
        data = response.json()
        assert "detail" in data
        assert (
            "entreprise" in data["detail"].lower()
            or "company" in data["detail"].lower()
        )

    def test_post_simulations_returns_403(self, client_no_company: TestClient):
        """POST /api/participation/simulations sans company → 403."""
        response = client_no_company.post(
            "/api/participation/simulations",
            json={
                "year": 2024,
                "simulation_name": "Test",
                "benefice_net": 0,
                "capitaux_propres": 0,
                "salaires_bruts": 0,
                "valeur_ajoutee": 0,
                "participation_mode": "uniforme",
                "results_data": {},
            },
        )
        assert response.status_code == 403


class TestParticipationGetEmployeeData:
    """GET /api/participation/employee-data/{year}."""

    @pytest.fixture
    def client_with_user(self, client: TestClient):
        from app.modules.participation.api.dependencies import get_current_user

        app.dependency_overrides[get_current_user] = lambda: _make_user_with_company()
        try:
            yield client
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    @patch("app.modules.participation.application.queries.get_participation_service")
    def test_returns_200_and_employee_list(
        self, mock_get_service, client_with_user: TestClient
    ):
        """Avec utilisateur et company : 200 et liste employés (mockée)."""
        mock_svc = MagicMock()
        mock_svc.get_employee_participation_data.return_value = []
        mock_get_service.return_value = mock_svc

        response = client_with_user.get("/api/participation/employee-data/2024")

        assert response.status_code == 200
        data = response.json()
        assert "employees" in data
        assert data["year"] == 2024
        assert isinstance(data["employees"], list)

    @patch("app.modules.participation.application.queries.get_participation_service")
    def test_returns_employees_with_expected_fields(
        self, mock_get_service, client_with_user: TestClient
    ):
        """Réponse contient les champs attendus par employé."""
        from app.modules.participation.application.dto import EmployeeParticipationRow

        mock_svc = MagicMock()
        mock_svc.get_employee_participation_data.return_value = [
            EmployeeParticipationRow(
                employee_id="emp-1",
                first_name="Jean",
                last_name="Dupont",
                annual_salary=36000.0,
                presence_days=200,
                seniority_years=2,
                has_real_salary=True,
                has_real_presence=True,
            ),
        ]
        mock_get_service.return_value = mock_svc

        response = client_with_user.get("/api/participation/employee-data/2024")

        assert response.status_code == 200
        data = response.json()
        assert len(data["employees"]) == 1
        emp = data["employees"][0]
        assert emp["employee_id"] == "emp-1"
        assert emp["first_name"] == "Jean"
        assert emp["annual_salary"] == 36000.0
        assert emp["presence_days"] == 200
        assert emp["has_real_salary"] is True


class TestParticipationSimulationsList:
    """GET /api/participation/simulations."""

    @pytest.fixture
    def client_with_user(self, client: TestClient):
        from app.modules.participation.api.dependencies import get_current_user

        app.dependency_overrides[get_current_user] = lambda: _make_user_with_company()
        try:
            yield client
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    @patch("app.modules.participation.application.queries.get_participation_service")
    def test_list_returns_200_and_array(
        self, mock_get_service, client_with_user: TestClient
    ):
        """GET /api/participation/simulations → 200 et liste (tableau)."""
        mock_svc = MagicMock()
        mock_svc.list_simulations.return_value = []
        mock_get_service.return_value = mock_svc

        response = client_with_user.get("/api/participation/simulations")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    @patch("app.modules.participation.application.queries.get_participation_service")
    def test_list_accepts_year_query(
        self, mock_get_service, client_with_user: TestClient
    ):
        """GET /api/participation/simulations?year=2024 transmet le filtre."""
        mock_svc = MagicMock()
        mock_svc.list_simulations.return_value = []
        mock_get_service.return_value = mock_svc

        client_with_user.get("/api/participation/simulations?year=2024")

        mock_svc.list_simulations.assert_called_once()
        call_args = mock_svc.list_simulations.call_args[0]
        assert call_args[0] == TEST_COMPANY_ID
        assert call_args[1] == 2024


class TestParticipationSimulationCreate:
    """POST /api/participation/simulations."""

    @pytest.fixture
    def client_with_user(self, client: TestClient):
        from app.modules.participation.api.dependencies import get_current_user

        app.dependency_overrides[get_current_user] = lambda: _make_user_with_company()
        try:
            yield client
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    @patch("app.modules.participation.application.commands.get_participation_service")
    def test_create_returns_201_and_entity(
        self, mock_get_service, client_with_user: TestClient
    ):
        """POST avec body valide → 200 et simulation créée (mock)."""
        from app.modules.participation.domain.entities import ParticipationSimulation
        from app.modules.participation.domain.enums import DistributionMode

        created = ParticipationSimulation(
            id=uuid4(),
            company_id=uuid4(),
            year=2024,
            simulation_name="Nouvelle sim",
            benefice_net=100000.0,
            capitaux_propres=500000.0,
            salaires_bruts=300000.0,
            valeur_ajoutee=400000.0,
            participation_mode=DistributionMode.UNIFORME,
            participation_salaire_percent=50,
            participation_presence_percent=50,
            interessement_enabled=False,
            interessement_envelope=None,
            interessement_mode=None,
            interessement_salaire_percent=50,
            interessement_presence_percent=50,
            results_data={},
            created_at=datetime.now(),
            created_by=uuid4(),
            updated_at=datetime.now(),
        )
        mock_svc = MagicMock()
        mock_svc.create_simulation.return_value = created
        mock_get_service.return_value = mock_svc

        response = client_with_user.post(
            "/api/participation/simulations",
            json={
                "year": 2024,
                "simulation_name": "Nouvelle sim",
                "benefice_net": 100000,
                "capitaux_propres": 500000,
                "salaires_bruts": 300000,
                "valeur_ajoutee": 400000,
                "participation_mode": "uniforme",
                "participation_salaire_percent": 50,
                "participation_presence_percent": 50,
                "interessement_enabled": False,
                "interessement_salaire_percent": 50,
                "interessement_presence_percent": 50,
                "results_data": {},
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["simulation_name"] == "Nouvelle sim"
        assert data["year"] == 2024

    @patch("app.modules.participation.application.commands.get_participation_service")
    def test_create_duplicate_name_returns_400(
        self, mock_get_service, client_with_user: TestClient
    ):
        """POST avec un nom de simulation déjà existant pour l'année → 400."""
        from app.modules.participation.application.service import (
            DuplicateSimulationNameError,
        )

        mock_svc = MagicMock()
        mock_svc.create_simulation.side_effect = DuplicateSimulationNameError(
            "Doublon", 2024
        )
        mock_get_service.return_value = mock_svc

        response = client_with_user.post(
            "/api/participation/simulations",
            json={
                "year": 2024,
                "simulation_name": "Doublon",
                "benefice_net": 0,
                "capitaux_propres": 0,
                "salaires_bruts": 0,
                "valeur_ajoutee": 0,
                "participation_mode": "uniforme",
                "results_data": {},
            },
        )

        assert response.status_code == 400
        assert "Doublon" in response.json().get("detail", "")
        assert "2024" in response.json().get("detail", "")

    def test_create_invalid_body_returns_422(self, client: TestClient):
        """POST sans champs requis → 422 (validation Pydantic)."""
        from app.modules.participation.api.dependencies import get_current_user

        app.dependency_overrides[get_current_user] = lambda: _make_user_with_company()
        try:
            response = client.post(
                "/api/participation/simulations",
                json={"year": 2024},
            )
            assert response.status_code == 422
        finally:
            app.dependency_overrides.pop(get_current_user, None)


class TestParticipationSimulationGetById:
    """GET /api/participation/simulations/{simulation_id}."""

    @pytest.fixture
    def client_with_user(self, client: TestClient):
        from app.modules.participation.api.dependencies import get_current_user

        app.dependency_overrides[get_current_user] = lambda: _make_user_with_company()
        try:
            yield client
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    @patch("app.modules.participation.application.queries.get_participation_service")
    def test_get_by_id_returns_404_when_not_found(
        self, mock_get_service, client_with_user: TestClient
    ):
        """GET /api/participation/simulations/{id} quand simulation inexistante → 404."""
        mock_svc = MagicMock()
        mock_svc.get_simulation.return_value = None
        mock_get_service.return_value = mock_svc

        response = client_with_user.get(
            "/api/participation/simulations/00000000-0000-0000-0000-000000000000"
        )

        assert response.status_code == 404
        assert "detail" in response.json()

    @patch("app.modules.participation.application.queries.get_participation_service")
    def test_get_by_id_returns_200_when_found(
        self, mock_get_service, client_with_user: TestClient
    ):
        """GET /api/participation/simulations/{id} quand trouvé → 200."""
        from app.modules.participation.domain.entities import ParticipationSimulation
        from app.modules.participation.domain.enums import DistributionMode

        sim_id = uuid4()
        entity = ParticipationSimulation(
            id=sim_id,
            company_id=uuid4(),
            year=2024,
            simulation_name="Ma sim",
            benefice_net=0.0,
            capitaux_propres=0.0,
            salaires_bruts=0.0,
            valeur_ajoutee=0.0,
            participation_mode=DistributionMode.UNIFORME,
            participation_salaire_percent=50,
            participation_presence_percent=50,
            interessement_enabled=False,
            interessement_envelope=None,
            interessement_mode=None,
            interessement_salaire_percent=50,
            interessement_presence_percent=50,
            results_data={},
            created_at=datetime.now(),
            created_by=None,
            updated_at=datetime.now(),
        )
        mock_svc = MagicMock()
        mock_svc.get_simulation.return_value = entity
        mock_get_service.return_value = mock_svc

        response = client_with_user.get(f"/api/participation/simulations/{sim_id}")

        assert response.status_code == 200
        assert response.json()["simulation_name"] == "Ma sim"
        assert response.json()["year"] == 2024


class TestParticipationSimulationDelete:
    """DELETE /api/participation/simulations/{simulation_id}."""

    @pytest.fixture
    def client_with_user(self, client: TestClient):
        from app.modules.participation.api.dependencies import get_current_user

        app.dependency_overrides[get_current_user] = lambda: _make_user_with_company()
        try:
            yield client
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    @patch("app.modules.participation.application.commands.get_participation_service")
    def test_delete_returns_404_when_not_found(
        self, mock_get_service, client_with_user: TestClient
    ):
        """DELETE quand simulation inexistante → 404."""
        mock_svc = MagicMock()
        mock_svc.delete_simulation.return_value = False
        mock_get_service.return_value = mock_svc

        response = client_with_user.delete(
            "/api/participation/simulations/00000000-0000-0000-0000-000000000000"
        )

        assert response.status_code == 404

    @patch("app.modules.participation.application.commands.get_participation_service")
    def test_delete_returns_200_and_message_when_deleted(
        self, mock_get_service, client_with_user: TestClient
    ):
        """DELETE quand simulation trouvée → 200 et message succès."""
        mock_svc = MagicMock()
        mock_svc.delete_simulation.return_value = True
        mock_get_service.return_value = mock_svc

        response = client_with_user.delete(
            "/api/participation/simulations/550e8400-e29b-41d4-a716-446655440099"
        )

        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert (
            "supprim" in data["message"].lower() or "success" in data["message"].lower()
        )
