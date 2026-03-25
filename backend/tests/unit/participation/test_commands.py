"""
Tests unitaires des commandes participation (application/commands.py).

Repositories et service mockés ; pas de DB ni HTTP.
"""

from datetime import datetime
from uuid import uuid4
from unittest.mock import MagicMock

import pytest

from app.modules.participation.application.commands import (
    create_participation_simulation,
    delete_participation_simulation,
)
from app.modules.participation.application.dto import SimulationCreateInput
from app.modules.participation.application.service import DuplicateSimulationNameError
from app.modules.participation.domain.entities import ParticipationSimulation
from app.modules.participation.domain.enums import DistributionMode


COMPANY_ID = "550e8400-e29b-41d4-a716-446655440000"
USER_ID = "660e8400-e29b-41d4-a716-446655440001"


def _make_create_input(
    simulation_name: str = "Sim test",
    year: int = 2024,
    company_id: str = COMPANY_ID,
    created_by: str = USER_ID,
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
        results_data={"participants": []},
        company_id=company_id,
        created_by=created_by,
    )


def _make_entity(sim_id: str = None, name: str = "Sim test"):
    sim_id = sim_id or str(uuid4())
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


class TestCreateParticipationSimulation:
    """Commande create_participation_simulation."""

    def test_create_returns_entity_from_service(self):
        """Crée une simulation et retourne l'entité renvoyée par le service."""
        input_data = _make_create_input()
        expected = _make_entity(name="Sim test")
        mock_service = MagicMock()
        mock_service.create_simulation.return_value = expected

        result = create_participation_simulation(input_data, service=mock_service)

        mock_service.create_simulation.assert_called_once_with(input_data)
        assert result is expected
        assert result.simulation_name == "Sim test"

    def test_create_raises_duplicate_name_error_when_service_raises(self):
        """Lève DuplicateSimulationNameError si le service lève (nom déjà existant)."""
        input_data = _make_create_input(simulation_name="Doublon")
        mock_service = MagicMock()
        mock_service.create_simulation.side_effect = DuplicateSimulationNameError(
            "Doublon", 2024
        )

        with pytest.raises(DuplicateSimulationNameError) as exc_info:
            create_participation_simulation(input_data, service=mock_service)

        assert exc_info.value.simulation_name == "Doublon"
        assert exc_info.value.year == 2024


class TestDeleteParticipationSimulation:
    """Commande delete_participation_simulation."""

    def test_delete_returns_true_when_service_returns_true(self):
        """Suppression réussie → True."""
        mock_service = MagicMock()
        mock_service.delete_simulation.return_value = True

        result = delete_participation_simulation(
            "sim-123", COMPANY_ID, service=mock_service
        )

        mock_service.delete_simulation.assert_called_once_with("sim-123", COMPANY_ID)
        assert result is True

    def test_delete_returns_false_when_service_returns_false(self):
        """Simulation non trouvée → False."""
        mock_service = MagicMock()
        mock_service.delete_simulation.return_value = False

        result = delete_participation_simulation(
            "sim-unknown", COMPANY_ID, service=mock_service
        )

        mock_service.delete_simulation.assert_called_once_with(
            "sim-unknown", COMPANY_ID
        )
        assert result is False
