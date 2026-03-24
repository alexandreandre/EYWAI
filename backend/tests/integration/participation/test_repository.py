"""
Tests d'intégration du repository participation (ParticipationSimulationRepository).

Sans DB de test : mocks Supabase pour valider la logique et les appels.
Avec DB de test : prévoir la fixture db_session (conftest) et des données
dans participation_simulations pour des tests CRUD réels.
"""
from datetime import datetime
from uuid import uuid4
from unittest.mock import MagicMock, patch

import pytest

from app.modules.participation.domain.entities import ParticipationSimulation
from app.modules.participation.domain.enums import DistributionMode
from app.modules.participation.infrastructure.repository import (
    ParticipationSimulationRepository,
)


pytestmark = pytest.mark.integration

COMPANY_ID = "550e8400-e29b-41d4-a716-446655440000"
USER_ID = "660e8400-e29b-41d4-a716-446655440001"


def _row(
    company_id: str = COMPANY_ID,
    simulation_name: str = "Sim test",
    year: int = 2024,
    sim_id: str = None,
    **kwargs,
):
    sim_id = sim_id or str(uuid4())
    base = {
        "id": sim_id,
        "company_id": company_id,
        "year": year,
        "simulation_name": simulation_name,
        "benefice_net": 100000.0,
        "capitaux_propres": 500000.0,
        "salaires_bruts": 300000.0,
        "valeur_ajoutee": 400000.0,
        "participation_mode": "combinaison",
        "participation_salaire_percent": 60,
        "participation_presence_percent": 40,
        "interessement_enabled": True,
        "interessement_envelope": 50000.0,
        "interessement_mode": "salaire",
        "interessement_salaire_percent": 100,
        "interessement_presence_percent": 0,
        "results_data": {},
        "created_at": datetime.now().isoformat(),
        "created_by": USER_ID,
        "updated_at": datetime.now().isoformat(),
    }
    base.update(kwargs)
    return base


class TestParticipationSimulationRepositoryCreate:
    """create."""

    def test_create_calls_insert_with_payload_and_returns_entity(self):
        with patch(
            "app.modules.participation.infrastructure.repository.supabase"
        ) as supabase:
            table = MagicMock()
            insert_chain = MagicMock()
            inserted_row = _row(simulation_name="Nouvelle")
            insert_chain.execute.return_value = MagicMock(data=[inserted_row])
            table.insert.return_value = insert_chain
            supabase.table.return_value = table

            repo = ParticipationSimulationRepository()
            data = {
                "company_id": COMPANY_ID,
                "year": 2024,
                "simulation_name": "Nouvelle",
                "benefice_net": 100000.0,
                "capitaux_propres": 500000.0,
                "salaires_bruts": 300000.0,
                "valeur_ajoutee": 400000.0,
                "participation_mode": "combinaison",
                "participation_salaire_percent": 60,
                "participation_presence_percent": 40,
                "interessement_enabled": True,
                "interessement_envelope": 50000.0,
                "interessement_mode": "salaire",
                "interessement_salaire_percent": 100,
                "interessement_presence_percent": 0,
                "results_data": {},
            }
            result = repo.create(data, USER_ID)

            table.insert.assert_called_once()
            call_payload = table.insert.call_args[0][0]
            assert call_payload["company_id"] == COMPANY_ID
            assert call_payload["simulation_name"] == "Nouvelle"
            assert call_payload["created_by"] == USER_ID
            assert isinstance(result, ParticipationSimulation)
            assert result.simulation_name == "Nouvelle"
            assert result.participation_mode == DistributionMode.COMBINAISON

    def test_create_raises_when_insert_returns_no_data(self):
        with patch(
            "app.modules.participation.infrastructure.repository.supabase"
        ) as supabase:
            table = MagicMock()
            insert_chain = MagicMock()
            insert_chain.execute.return_value = MagicMock(data=[])
            table.insert.return_value = insert_chain
            supabase.table.return_value = table

            repo = ParticipationSimulationRepository()
            data = {
                "company_id": COMPANY_ID,
                "year": 2024,
                "simulation_name": "X",
                "benefice_net": 0,
                "capitaux_propres": 0,
                "salaires_bruts": 0,
                "valeur_ajoutee": 0,
                "participation_mode": "uniforme",
                "participation_salaire_percent": 50,
                "participation_presence_percent": 50,
                "interessement_enabled": False,
                "interessement_envelope": None,
                "interessement_mode": None,
                "interessement_salaire_percent": 50,
                "interessement_presence_percent": 50,
                "results_data": {},
            }
            with pytest.raises(RuntimeError, match="Insert returned no data"):
                repo.create(data, USER_ID)


class TestParticipationSimulationRepositoryGetById:
    """get_by_id."""

    def test_get_by_id_returns_entity_when_found(self):
        sim_id = str(uuid4())
        row = _row(sim_id=sim_id, simulation_name="Ma sim")
        with patch(
            "app.modules.participation.infrastructure.repository.supabase"
        ) as supabase:
            table = MagicMock()
            chain = MagicMock()
            chain.eq.return_value = chain
            chain.single.return_value.execute.return_value = MagicMock(data=row)
            table.select.return_value = chain
            supabase.table.return_value = table

            repo = ParticipationSimulationRepository()
            result = repo.get_by_id(sim_id, COMPANY_ID)

            table.select.assert_called_once_with("*")
            chain.eq.assert_any_call("id", sim_id)
            chain.eq.assert_any_call("company_id", COMPANY_ID)
            assert result is not None
            assert result.simulation_name == "Ma sim"

    def test_get_by_id_returns_none_when_no_data(self):
        with patch(
            "app.modules.participation.infrastructure.repository.supabase"
        ) as supabase:
            table = MagicMock()
            chain = MagicMock()
            chain.eq.return_value = chain
            chain.single.return_value.execute.return_value = MagicMock(data=None)
            table.select.return_value = table
            supabase.table.return_value = table

            repo = ParticipationSimulationRepository()
            result = repo.get_by_id("00000000-0000-0000-0000-000000000000", COMPANY_ID)

            assert result is None


class TestParticipationSimulationRepositoryListByCompany:
    """list_by_company."""

    def test_list_by_company_calls_select_eq_order(self):
        with patch(
            "app.modules.participation.infrastructure.repository.supabase"
        ) as supabase:
            table = MagicMock()
            chain = MagicMock()
            chain.eq.return_value = chain
            chain.order.return_value = chain
            chain.execute.return_value = MagicMock(
                data=[
                    _row(simulation_name="A"),
                    _row(simulation_name="B"),
                ]
            )
            table.select.return_value = chain
            supabase.table.return_value = table

            repo = ParticipationSimulationRepository()
            result = repo.list_by_company(COMPANY_ID)

            table.select.assert_called_once_with("*")
            chain.eq.assert_called_with("company_id", COMPANY_ID)
            assert len(result) == 2
            assert all(isinstance(e, ParticipationSimulation) for e in result)
            assert result[0].simulation_name == "A"
            assert result[1].simulation_name == "B"

    def test_list_by_company_with_year_filters_by_year(self):
        with patch(
            "app.modules.participation.infrastructure.repository.supabase"
        ) as supabase:
            table = MagicMock()
            chain = MagicMock()
            chain.eq.return_value = chain
            chain.order.return_value = chain
            chain.execute.return_value = MagicMock(data=[])
            table.select.return_value = chain
            supabase.table.return_value = table

            repo = ParticipationSimulationRepository()
            repo.list_by_company(COMPANY_ID, year=2024)

            assert chain.eq.call_count >= 2
            eq_calls = [c[0] for c in chain.eq.call_args_list]
            assert ("company_id", COMPANY_ID) in eq_calls
            assert ("year", 2024) in eq_calls

    def test_list_by_company_empty_data_returns_empty_list(self):
        with patch(
            "app.modules.participation.infrastructure.repository.supabase"
        ) as supabase:
            table = MagicMock()
            chain = MagicMock()
            chain.eq.return_value = chain
            chain.order.return_value = chain
            chain.execute.return_value = MagicMock(data=[])
            table.select.return_value = chain
            supabase.table.return_value = table

            repo = ParticipationSimulationRepository()
            result = repo.list_by_company(COMPANY_ID)

            assert result == []


class TestParticipationSimulationRepositoryDelete:
    """delete."""

    def test_delete_returns_false_when_not_found(self):
        with patch(
            "app.modules.participation.infrastructure.repository.supabase"
        ) as supabase:
            table = MagicMock()
            select_chain = MagicMock()
            select_chain.eq.return_value = select_chain
            select_chain.execute.return_value = MagicMock(data=[])
            table.select.return_value = select_chain
            supabase.table.return_value = table

            repo = ParticipationSimulationRepository()
            result = repo.delete("sim-unknown", COMPANY_ID)

            assert result is False
            table.delete.assert_not_called()

    def test_delete_returns_true_and_calls_delete_when_found(self):
        sim_id = str(uuid4())
        with patch(
            "app.modules.participation.infrastructure.repository.supabase"
        ) as supabase:
            table = MagicMock()
            select_chain = MagicMock()
            select_chain.eq.return_value = select_chain
            select_chain.execute.return_value = MagicMock(data=[{"id": sim_id}])
            table.select.return_value = select_chain
            delete_chain = MagicMock()
            table.delete.return_value = delete_chain
            delete_chain.eq.return_value.execute.return_value = None
            supabase.table.return_value = table

            repo = ParticipationSimulationRepository()
            result = repo.delete(sim_id, COMPANY_ID)

            assert result is True
            table.delete.assert_called_once()
            delete_chain.eq.assert_called_once_with("id", sim_id)


class TestParticipationSimulationRepositoryExistsWithName:
    """exists_with_name."""

    def test_exists_with_name_returns_true_when_data(self):
        with patch(
            "app.modules.participation.infrastructure.repository.supabase"
        ) as supabase:
            table = MagicMock()
            chain = MagicMock()
            chain.eq.return_value = chain
            chain.execute.return_value = MagicMock(data=[{"id": str(uuid4())}])
            table.select.return_value = chain
            supabase.table.return_value = table

            repo = ParticipationSimulationRepository()
            result = repo.exists_with_name(COMPANY_ID, 2024, "Doublon")

            table.select.assert_called_once_with("id")
            assert chain.eq.call_count == 3
            assert result is True

    def test_exists_with_name_returns_false_when_no_data(self):
        with patch(
            "app.modules.participation.infrastructure.repository.supabase"
        ) as supabase:
            table = MagicMock()
            chain = MagicMock()
            chain.eq.return_value = chain
            chain.execute.return_value = MagicMock(data=[])
            table.select.return_value = chain
            supabase.table.return_value = table

            repo = ParticipationSimulationRepository()
            result = repo.exists_with_name(COMPANY_ID, 2024, "Unique")

            assert result is False
