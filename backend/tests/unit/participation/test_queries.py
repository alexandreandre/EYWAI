"""
Tests unitaires des queries participation (application/queries.py).

Service mocké ; pas de DB ni HTTP.
"""
from datetime import datetime
from uuid import uuid4
from unittest.mock import MagicMock


from app.modules.participation.application.dto import EmployeeParticipationRow
from app.modules.participation.application.queries import (
    get_employee_participation_data,
    list_participation_simulations,
    get_participation_simulation,
)
from app.modules.participation.domain.entities import ParticipationSimulation
from app.modules.participation.domain.enums import DistributionMode


COMPANY_ID = "550e8400-e29b-41d4-a716-446655440000"


def _make_simulation(sim_id: str = None, name: str = "Sim"):
    return ParticipationSimulation(
        id=sim_id or uuid4(),
        company_id=uuid4(),
        year=2024,
        simulation_name=name,
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


class TestGetEmployeeParticipationData:
    """Query get_employee_participation_data."""

    def test_returns_list_from_service(self):
        """Retourne la liste de EmployeeParticipationRow fournie par le service."""
        rows = [
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
        mock_service = MagicMock()
        mock_service.get_employee_participation_data.return_value = rows

        result = get_employee_participation_data(
            COMPANY_ID, 2024, service=mock_service
        )

        mock_service.get_employee_participation_data.assert_called_once_with(
            COMPANY_ID, 2024
        )
        assert len(result) == 1
        assert result[0].employee_id == "emp-1"
        assert result[0].annual_salary == 36000.0
        assert result[0].presence_days == 200

    def test_empty_list_when_no_employees(self):
        """Liste vide quand le service retourne une liste vide."""
        mock_service = MagicMock()
        mock_service.get_employee_participation_data.return_value = []

        result = get_employee_participation_data(
            COMPANY_ID, 2025, service=mock_service
        )

        assert result == []


class TestListParticipationSimulations:
    """Query list_participation_simulations."""

    def test_returns_list_from_service(self):
        """Retourne la liste d'entités fournie par le service."""
        sims = [_make_simulation(name="A"), _make_simulation(name="B")]
        mock_service = MagicMock()
        mock_service.list_simulations.return_value = sims

        result = list_participation_simulations(COMPANY_ID, service=mock_service)

        mock_service.list_simulations.assert_called_once_with(COMPANY_ID, None)
        assert len(result) == 2
        assert result[0].simulation_name == "A"
        assert result[1].simulation_name == "B"

    def test_passes_year_filter_to_service(self):
        """Transmet le filtre year au service."""
        mock_service = MagicMock()
        mock_service.list_simulations.return_value = []

        list_participation_simulations(
            COMPANY_ID, year=2024, service=mock_service
        )

        mock_service.list_simulations.assert_called_once_with(COMPANY_ID, 2024)

    def test_empty_list_when_none(self):
        """Liste vide quand le service retourne une liste vide."""
        mock_service = MagicMock()
        mock_service.list_simulations.return_value = []

        result = list_participation_simulations(COMPANY_ID, service=mock_service)

        assert result == []


class TestGetParticipationSimulation:
    """Query get_participation_simulation."""

    def test_returns_entity_when_found(self):
        """Retourne l'entité quand le service la trouve."""
        sim = _make_simulation(name="Ma sim")
        mock_service = MagicMock()
        mock_service.get_simulation.return_value = sim

        result = get_participation_simulation(
            "sim-123", COMPANY_ID, service=mock_service
        )

        mock_service.get_simulation.assert_called_once_with("sim-123", COMPANY_ID)
        assert result is sim
        assert result.simulation_name == "Ma sim"

    def test_returns_none_when_not_found(self):
        """Retourne None quand le service ne trouve pas la simulation."""
        mock_service = MagicMock()
        mock_service.get_simulation.return_value = None

        result = get_participation_simulation(
            "sim-unknown", COMPANY_ID, service=mock_service
        )

        mock_service.get_simulation.assert_called_once_with(
            "sim-unknown", COMPANY_ID
        )
        assert result is None
