"""
Tests unitaires du service applicatif participation (application/service.py).

Repository et requêtes infra mockés ; pas de DB réelle.
"""
from datetime import datetime
from uuid import uuid4
from unittest.mock import MagicMock, patch

import pytest

from app.modules.participation.application.dto import (
    EmployeeParticipationRow,
    SimulationCreateInput,
)
from app.modules.participation.application.service import (
    DuplicateSimulationNameError,
    ParticipationService,
)
from app.modules.participation.domain.entities import ParticipationSimulation
from app.modules.participation.domain.enums import DistributionMode


COMPANY_ID = "550e8400-e29b-41d4-a716-446655440000"
USER_ID = "660e8400-e29b-41d4-a716-446655440001"


def _make_create_input(
    simulation_name: str = "Sim test",
    year: int = 2024,
) -> SimulationCreateInput:
    return SimulationCreateInput(
        year=year,
        simulation_name=simulation_name,
        benefice_net=100000.0,
        capitaux_propres=500000.0,
        salaires_bruts=300000.0,
        valeur_ajoutee=400000.0,
        participation_mode="combinaison",
        participation_salaire_percent=60,
        participation_presence_percent=40,
        interessement_enabled=True,
        interessement_envelope=50000.0,
        interessement_mode="salaire",
        interessement_salaire_percent=100,
        interessement_presence_percent=0,
        results_data={},
        company_id=COMPANY_ID,
        created_by=USER_ID,
    )


def _make_entity(name: str = "Sim test"):
    return ParticipationSimulation(
        id=uuid4(),
        company_id=uuid4(),
        year=2024,
        simulation_name=name,
        benefice_net=100000.0,
        capitaux_propres=500000.0,
        salaires_bruts=300000.0,
        valeur_ajoutee=400000.0,
        participation_mode=DistributionMode.COMBINAISON,
        participation_salaire_percent=60,
        participation_presence_percent=40,
        interessement_enabled=True,
        interessement_envelope=50000.0,
        interessement_mode=DistributionMode.SALAIRE,
        interessement_salaire_percent=100,
        interessement_presence_percent=0,
        results_data={},
        created_at=datetime.now(),
        created_by=uuid4(),
        updated_at=datetime.now(),
    )


class TestParticipationServiceGetEmployeeParticipationData:
    """ParticipationService.get_employee_participation_data."""

    @patch("app.modules.participation.application.service.fetch_employee_participation_data")
    def test_delegates_to_fetch_and_maps_to_rows(self, mock_fetch):
        """Délègue à fetch_employee_participation_data et mappe en EmployeeParticipationRow."""
        mock_fetch.return_value = [
            {
                "employee_id": "emp-1",
                "first_name": "Jean",
                "last_name": "Dupont",
                "annual_salary": 36000.5,
                "presence_days": 200,
                "seniority_years": 3,
                "has_real_salary": True,
                "has_real_presence": True,
            },
        ]
        service = ParticipationService()

        result = service.get_employee_participation_data(COMPANY_ID, 2024)

        mock_fetch.assert_called_once_with(COMPANY_ID, 2024)
        assert len(result) == 1
        assert isinstance(result[0], EmployeeParticipationRow)
        assert result[0].employee_id == "emp-1"
        assert result[0].first_name == "Jean"
        assert result[0].annual_salary == 36000.5
        assert result[0].presence_days == 200
        assert result[0].has_real_salary is True

    @patch("app.modules.participation.application.service.fetch_employee_participation_data")
    def test_empty_list_when_fetch_returns_empty(self, mock_fetch):
        """Liste vide quand fetch retourne une liste vide."""
        mock_fetch.return_value = []
        service = ParticipationService()

        result = service.get_employee_participation_data(COMPANY_ID, 2025)

        assert result == []


class TestParticipationServiceCreateSimulation:
    """ParticipationService.create_simulation."""

    def test_creates_via_repo_when_name_does_not_exist(self):
        """Crée une simulation via le repository quand le nom n'existe pas."""
        input_data = _make_create_input()
        expected = _make_entity()
        mock_repo = MagicMock()
        mock_repo.exists_with_name.return_value = False
        mock_repo.create.return_value = expected
        service = ParticipationService(simulation_repository=mock_repo)

        result = service.create_simulation(input_data)

        mock_repo.exists_with_name.assert_called_once_with(
            COMPANY_ID, 2024, "Sim test"
        )
        mock_repo.create.assert_called_once()
        call_data = mock_repo.create.call_args[0][0]
        assert call_data["company_id"] == COMPANY_ID
        assert call_data["year"] == 2024
        assert call_data["simulation_name"] == "Sim test"
        assert result is expected

    def test_raises_duplicate_error_when_name_exists(self):
        """Lève DuplicateSimulationNameError si exists_with_name retourne True."""
        input_data = _make_create_input(simulation_name="Doublon")
        mock_repo = MagicMock()
        mock_repo.exists_with_name.return_value = True
        service = ParticipationService(simulation_repository=mock_repo)

        with pytest.raises(DuplicateSimulationNameError) as exc_info:
            service.create_simulation(input_data)

        assert exc_info.value.simulation_name == "Doublon"
        assert exc_info.value.year == 2024
        mock_repo.create.assert_not_called()


class TestParticipationServiceListSimulations:
    """ParticipationService.list_simulations."""

    def test_delegates_to_repo(self):
        """Délègue au repository list_by_company."""
        sims = [_make_entity("A"), _make_entity("B")]
        mock_repo = MagicMock()
        mock_repo.list_by_company.return_value = sims
        service = ParticipationService(simulation_repository=mock_repo)

        result = service.list_simulations(COMPANY_ID, year=2024)

        mock_repo.list_by_company.assert_called_once_with(COMPANY_ID, 2024)
        assert result == sims

    def test_list_without_year_filter(self):
        """list_simulations sans année appelle le repo avec year=None."""
        mock_repo = MagicMock()
        mock_repo.list_by_company.return_value = []
        service = ParticipationService(simulation_repository=mock_repo)

        service.list_simulations(COMPANY_ID)

        mock_repo.list_by_company.assert_called_once_with(COMPANY_ID, None)


class TestParticipationServiceGetSimulation:
    """ParticipationService.get_simulation."""

    def test_delegates_to_repo(self):
        """Délègue au repository get_by_id."""
        sim = _make_entity()
        mock_repo = MagicMock()
        mock_repo.get_by_id.return_value = sim
        service = ParticipationService(simulation_repository=mock_repo)

        result = service.get_simulation("sim-123", COMPANY_ID)

        mock_repo.get_by_id.assert_called_once_with("sim-123", COMPANY_ID)
        assert result is sim

    def test_returns_none_when_repo_returns_none(self):
        """Retourne None quand le repository retourne None."""
        mock_repo = MagicMock()
        mock_repo.get_by_id.return_value = None
        service = ParticipationService(simulation_repository=mock_repo)

        result = service.get_simulation("sim-unknown", COMPANY_ID)

        assert result is None


class TestParticipationServiceDeleteSimulation:
    """ParticipationService.delete_simulation."""

    def test_delegates_to_repo_returns_true(self):
        """Délègue au repository et retourne True si supprimé."""
        mock_repo = MagicMock()
        mock_repo.delete.return_value = True
        service = ParticipationService(simulation_repository=mock_repo)

        result = service.delete_simulation("sim-123", COMPANY_ID)

        mock_repo.delete.assert_called_once_with("sim-123", COMPANY_ID)
        assert result is True

    def test_returns_false_when_repo_returns_false(self):
        """Retourne False quand le repository retourne False."""
        mock_repo = MagicMock()
        mock_repo.delete.return_value = False
        service = ParticipationService(simulation_repository=mock_repo)

        result = service.delete_simulation("sim-unknown", COMPANY_ID)

        assert result is False


class TestDuplicateSimulationNameError:
    """Exception DuplicateSimulationNameError."""

    def test_has_simulation_name_and_year(self):
        """Expose simulation_name et year et message explicite."""
        err = DuplicateSimulationNameError("Ma sim", 2024)
        assert err.simulation_name == "Ma sim"
        assert err.year == 2024
        assert "Ma sim" in str(err)
        assert "2024" in str(err)
