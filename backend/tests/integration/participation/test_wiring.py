"""
Tests de câblage (wiring) du module participation : injection des dépendances et flux bout en bout.

Vérifie que les commands/queries utilisent bien le service, que le service utilise
le repository et les requêtes infra, et que le routeur appelle les bons cas d'usage.
"""

from datetime import datetime
from uuid import uuid4
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.participation.application.commands import (
    create_participation_simulation,
    delete_participation_simulation,
)
from app.modules.participation.application.queries import (
    get_employee_participation_data,
    get_participation_simulation,
    list_participation_simulations,
)
from app.modules.participation.application.dto import SimulationCreateInput
from app.modules.participation.application.service import (
    DuplicateSimulationNameError,
    ParticipationService,
)
from app.modules.participation.domain.entities import ParticipationSimulation
from app.modules.participation.domain.enums import DistributionMode


pytestmark = pytest.mark.integration

COMPANY_ID = "550e8400-e29b-41d4-a716-446655440000"
USER_ID = "660e8400-e29b-41d4-a716-446655440001"


class TestCommandsUseService:
    """Les commandes délèguent au ParticipationService."""

    def test_create_participation_simulation_uses_injected_service(self):
        """create_participation_simulation utilise le service injecté."""
        input_data = SimulationCreateInput(
            year=2024,
            simulation_name="Wired",
            benefice_net=0,
            capitaux_propres=0,
            salaires_bruts=0,
            valeur_ajoutee=0,
            participation_mode="uniforme",
            participation_salaire_percent=50,
            participation_presence_percent=50,
            interessement_enabled=False,
            interessement_envelope=None,
            interessement_mode=None,
            interessement_salaire_percent=50,
            interessement_presence_percent=50,
            results_data={},
            company_id=COMPANY_ID,
            created_by=USER_ID,
        )
        expected = ParticipationSimulation(
            id=uuid4(),
            company_id=uuid4(),
            year=2024,
            simulation_name="Wired",
            benefice_net=0,
            capitaux_propres=0,
            salaires_bruts=0,
            valeur_ajoutee=0,
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
        mock_svc.create_simulation.return_value = expected

        result = create_participation_simulation(input_data, service=mock_svc)

        mock_svc.create_simulation.assert_called_once_with(input_data)
        assert result is expected

    def test_delete_participation_simulation_uses_injected_service(self):
        """delete_participation_simulation utilise le service injecté."""
        mock_svc = MagicMock()
        mock_svc.delete_simulation.return_value = True

        result = delete_participation_simulation(
            "sim-123", COMPANY_ID, service=mock_svc
        )

        mock_svc.delete_simulation.assert_called_once_with("sim-123", COMPANY_ID)
        assert result is True


class TestQueriesUseService:
    """Les queries délèguent au ParticipationService."""

    def test_get_employee_participation_data_uses_injected_service(self):
        """get_employee_participation_data utilise le service injecté."""
        mock_svc = MagicMock()
        mock_svc.get_employee_participation_data.return_value = []

        result = get_employee_participation_data(COMPANY_ID, 2024, service=mock_svc)

        mock_svc.get_employee_participation_data.assert_called_once_with(
            COMPANY_ID, 2024
        )
        assert result == []

    def test_list_participation_simulations_uses_injected_service(self):
        """list_participation_simulations utilise le service injecté."""
        mock_svc = MagicMock()
        mock_svc.list_simulations.return_value = []

        result = list_participation_simulations(COMPANY_ID, year=2024, service=mock_svc)

        mock_svc.list_simulations.assert_called_once_with(COMPANY_ID, 2024)
        assert result == []

    def test_get_participation_simulation_uses_injected_service(self):
        """get_participation_simulation utilise le service injecté."""
        mock_svc = MagicMock()
        mock_svc.get_simulation.return_value = None

        result = get_participation_simulation("sim-123", COMPANY_ID, service=mock_svc)

        mock_svc.get_simulation.assert_called_once_with("sim-123", COMPANY_ID)
        assert result is None


class TestServiceUsesRepository:
    """ParticipationService utilise le repository pour les simulations."""

    def test_create_simulation_checks_exists_then_calls_repo_create(self):
        """create_simulation appelle exists_with_name puis create sur le repo."""
        input_data = SimulationCreateInput(
            year=2024,
            simulation_name="Flow",
            benefice_net=0,
            capitaux_propres=0,
            salaires_bruts=0,
            valeur_ajoutee=0,
            participation_mode="uniforme",
            participation_salaire_percent=50,
            participation_presence_percent=50,
            interessement_enabled=False,
            interessement_envelope=None,
            interessement_mode=None,
            interessement_salaire_percent=50,
            interessement_presence_percent=50,
            results_data={},
            company_id=COMPANY_ID,
            created_by=USER_ID,
        )
        expected = ParticipationSimulation(
            id=uuid4(),
            company_id=uuid4(),
            year=2024,
            simulation_name="Flow",
            benefice_net=0,
            capitaux_propres=0,
            salaires_bruts=0,
            valeur_ajoutee=0,
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
        mock_repo = MagicMock()
        mock_repo.exists_with_name.return_value = False
        mock_repo.create.return_value = expected

        service = ParticipationService(simulation_repository=mock_repo)
        result = service.create_simulation(input_data)

        mock_repo.exists_with_name.assert_called_once_with(COMPANY_ID, 2024, "Flow")
        mock_repo.create.assert_called_once()
        assert result is expected

    def test_create_simulation_raises_when_exists(self):
        """create_simulation lève DuplicateSimulationNameError si exists_with_name True."""
        input_data = SimulationCreateInput(
            year=2024,
            simulation_name="Doublon",
            benefice_net=0,
            capitaux_propres=0,
            salaires_bruts=0,
            valeur_ajoutee=0,
            participation_mode="uniforme",
            participation_salaire_percent=50,
            participation_presence_percent=50,
            interessement_enabled=False,
            interessement_envelope=None,
            interessement_mode=None,
            interessement_salaire_percent=50,
            interessement_presence_percent=50,
            results_data={},
            company_id=COMPANY_ID,
            created_by=USER_ID,
        )
        mock_repo = MagicMock()
        mock_repo.exists_with_name.return_value = True

        service = ParticipationService(simulation_repository=mock_repo)
        with pytest.raises(DuplicateSimulationNameError) as exc_info:
            service.create_simulation(input_data)

        assert exc_info.value.simulation_name == "Doublon"
        mock_repo.create.assert_not_called()


class TestApiRouterCallsApplication:
    """Le routeur API appelle bien les commands/queries (flux bout en bout)."""

    @pytest.fixture
    def client_with_user(self, client: TestClient):
        from app.modules.participation.api.dependencies import get_current_user

        user = MagicMock()
        user.id = USER_ID
        user.active_company_id = COMPANY_ID
        app.dependency_overrides[get_current_user] = lambda: user
        try:
            yield client
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    @patch("app.modules.participation.application.queries.get_participation_service")
    def test_get_employee_data_route_invokes_query(
        self, mock_get_service, client_with_user: TestClient
    ):
        """GET /api/participation/employee-data/{year} déclenche get_employee_participation_data."""
        mock_svc = MagicMock()
        mock_svc.get_employee_participation_data.return_value = []
        mock_get_service.return_value = mock_svc

        response = client_with_user.get("/api/participation/employee-data/2024")

        assert response.status_code == 200
        mock_svc.get_employee_participation_data.assert_called_once_with(
            COMPANY_ID, 2024
        )

    @patch("app.modules.participation.application.queries.get_participation_service")
    def test_list_simulations_route_invokes_query(
        self, mock_get_service, client_with_user: TestClient
    ):
        """GET /api/participation/simulations déclenche list_participation_simulations."""
        mock_svc = MagicMock()
        mock_svc.list_simulations.return_value = []
        mock_get_service.return_value = mock_svc

        response = client_with_user.get("/api/participation/simulations?year=2024")

        assert response.status_code == 200
        mock_svc.list_simulations.assert_called_once_with(COMPANY_ID, 2024)

    @patch("app.modules.participation.application.commands.get_participation_service")
    def test_create_simulation_route_invokes_command(
        self, mock_get_service, client_with_user: TestClient
    ):
        """POST /api/participation/simulations déclenche create_participation_simulation."""
        created = ParticipationSimulation(
            id=uuid4(),
            company_id=uuid4(),
            year=2024,
            simulation_name="E2E",
            benefice_net=0,
            capitaux_propres=0,
            salaires_bruts=0,
            valeur_ajoutee=0,
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
                "simulation_name": "E2E",
                "benefice_net": 0,
                "capitaux_propres": 0,
                "salaires_bruts": 0,
                "valeur_ajoutee": 0,
                "participation_mode": "uniforme",
                "results_data": {},
            },
        )

        assert response.status_code == 200
        mock_svc.create_simulation.assert_called_once()
        call_input = mock_svc.create_simulation.call_args[0][0]
        assert call_input.simulation_name == "E2E"
        assert call_input.company_id == COMPANY_ID
        assert call_input.created_by == USER_ID
