"""
Tests d'intégration du repository medical_follow_up (MedicalObligationRepository).

Vérifie que le repository délègue correctement aux requêtes infrastructure
et retourne les données attendues. Les requêtes DB sont mockées (pas de DB réelle).
Pour des tests contre une DB de test, prévoir db_session et données dans
medical_follow_up_obligations, employees, companies.
"""
from unittest.mock import MagicMock, patch

import pytest

from app.modules.medical_follow_up.infrastructure.repository import MedicalObligationRepository


pytestmark = pytest.mark.integration


@pytest.fixture
def mock_supabase():
    """Client Supabase mock (non utilisé directement si on patch les queries)."""
    return MagicMock()


@pytest.fixture
def repo(mock_supabase):
    """Instance du repository à tester."""
    return MedicalObligationRepository(mock_supabase)


class TestMedicalObligationRepositoryListForCompany:
    """list_for_company."""

    def test_calls_infra_query_with_params(self, repo: MedicalObligationRepository):
        """Délègue à list_obligations_raw avec company_id et filtres."""
        with patch(
            "app.modules.medical_follow_up.infrastructure.repository.infra_queries.list_obligations_raw",
            return_value=[],
        ) as mock_query:
            repo.list_for_company(
                "co-1",
                employee_id="emp-1",
                visit_type="vip",
                status="a_faire",
                priority=1,
                due_from="2025-01-01",
                due_to="2025-12-31",
            )
            mock_query.assert_called_once()
            call_args = mock_query.call_args
            assert call_args[0][1] == "co-1"  # supabase, company_id
            assert call_args[1]["employee_id"] == "emp-1"
            assert call_args[1]["visit_type"] == "vip"
            assert call_args[1]["status"] == "a_faire"
            assert call_args[1]["priority"] == 1
            assert call_args[1]["due_from"] == "2025-01-01"
            assert call_args[1]["due_to"] == "2025-12-31"
            assert call_args[1]["with_employee_join"] is True

    def test_returns_data_from_query(self, repo: MedicalObligationRepository):
        """Retourne la liste renvoyée par la requête."""
        data = [
            {
                "id": "obl-1",
                "company_id": "co-1",
                "employee_id": "emp-1",
                "visit_type": "vip",
                "trigger_type": "periodicite_vip",
                "due_date": "2025-06-01",
                "priority": 1,
                "status": "a_faire",
                "rule_source": "legal",
            },
        ]
        with patch(
            "app.modules.medical_follow_up.infrastructure.repository.infra_queries.list_obligations_raw",
            return_value=data,
        ):
            result = repo.list_for_company("co-1")
        assert result == data
        assert len(result) == 1
        assert result[0]["id"] == "obl-1"


class TestMedicalObligationRepositoryGetKpis:
    """get_kpis."""

    def test_calls_get_obligations_rows_and_compute_kpis(self, repo: MedicalObligationRepository):
        """Délègue à get_obligations_rows_for_kpis puis compute_kpis_from_rows."""
        with patch(
            "app.modules.medical_follow_up.infrastructure.repository.infra_queries.get_obligations_rows_for_kpis",
            return_value=[
                {"due_date": "2025-03-01", "status": "a_faire", "completed_date": None},
                {"due_date": "2025-04-01", "status": "realisee", "completed_date": "2025-03-10"},
            ],
        ) as mock_get_rows:
            result = repo.get_kpis("co-1")
            mock_get_rows.assert_called_once()
        assert "overdue_count" in result
        assert "due_within_30_count" in result
        assert "active_total" in result
        assert "completed_this_month" in result
        assert isinstance(result["overdue_count"], int)


class TestMedicalObligationRepositoryMarkPlanified:
    """mark_planified."""

    def test_calls_update_obligation_planified(self, repo: MedicalObligationRepository):
        """Délègue à update_obligation_planified."""
        with patch(
            "app.modules.medical_follow_up.infrastructure.repository.infra_queries.update_obligation_planified",
        ) as mock_update:
            repo.mark_planified("obl-1", "co-1", "2025-04-15", "RDV fixé")
            mock_update.assert_called_once()
            call_args = mock_update.call_args
            assert call_args[0][1] == "obl-1"
            assert call_args[0][2] == "2025-04-15"
            assert call_args[0][3] == "RDV fixé"


class TestMedicalObligationRepositoryMarkCompleted:
    """mark_completed."""

    def test_calls_update_obligation_completed(self, repo: MedicalObligationRepository):
        """Délègue à update_obligation_completed."""
        with patch(
            "app.modules.medical_follow_up.infrastructure.repository.infra_queries.update_obligation_completed",
        ) as mock_update:
            repo.mark_completed("obl-1", "co-1", "2025-04-20", "Visite effectuée")
            mock_update.assert_called_once()
            call_args = mock_update.call_args
            assert call_args[0][1] == "obl-1"
            assert call_args[0][2] == "2025-04-20"
            assert call_args[0][3] == "Visite effectuée"


class TestMedicalObligationRepositoryObligationExists:
    """obligation_exists."""

    def test_returns_true_when_found(self, repo: MedicalObligationRepository):
        """get_obligation_by_id retourne une ligne → True."""
        with patch(
            "app.modules.medical_follow_up.infrastructure.repository.infra_queries.get_obligation_by_id",
            return_value={"id": "obl-1", "company_id": "co-1"},
        ):
            assert repo.obligation_exists("obl-1", "co-1") is True

    def test_returns_false_when_not_found(self, repo: MedicalObligationRepository):
        """get_obligation_by_id retourne None → False."""
        with patch(
            "app.modules.medical_follow_up.infrastructure.repository.infra_queries.get_obligation_by_id",
            return_value=None,
        ):
            assert repo.obligation_exists("obl-unknown", "co-1") is False


class TestMedicalObligationRepositoryCreateOnDemand:
    """create_on_demand."""

    def test_calls_insert_obligation_with_payload(self, repo: MedicalObligationRepository):
        """Délègue à insert_obligation avec le payload attendu (visit_type=demande, etc.)."""
        with patch(
            "app.modules.medical_follow_up.infrastructure.repository.infra_queries.insert_obligation",
        ) as mock_insert:
            repo.create_on_demand("co-1", "emp-1", "Demande salarié", "2025-03-17")
            mock_insert.assert_called_once()
            payload = mock_insert.call_args[0][1]
            assert payload["company_id"] == "co-1"
            assert payload["employee_id"] == "emp-1"
            assert payload["visit_type"] == "demande"
            assert payload["trigger_type"] == "demande"
            assert payload["due_date"] == "2025-03-17"
            assert payload["status"] == "a_faire"
            assert payload["request_motif"] == "Demande salarié"
            assert payload["request_date"] == "2025-03-17"
            assert payload["priority"] == 3
            assert payload["rule_source"] == "legal"


class TestMedicalObligationRepositoryListForEmployee:
    """list_for_employee."""

    def test_calls_list_obligations_raw_with_employee_join(self, repo: MedicalObligationRepository):
        """Délègue à list_obligations_raw avec employee_id et with_employee_join=True."""
        with patch(
            "app.modules.medical_follow_up.infrastructure.repository.infra_queries.list_obligations_raw",
            return_value=[],
        ) as mock_query:
            repo.list_for_employee("co-1", "emp-1")
            mock_query.assert_called_once()
            assert mock_query.call_args[1]["employee_id"] == "emp-1"
            assert mock_query.call_args[1]["with_employee_join"] is True


class TestMedicalObligationRepositoryListForEmployeeNoJoin:
    """list_for_employee_no_join."""

    def test_calls_list_obligations_raw_without_employee_join(
        self, repo: MedicalObligationRepository
    ):
        """Délègue à list_obligations_raw avec with_employee_join=False."""
        with patch(
            "app.modules.medical_follow_up.infrastructure.repository.infra_queries.list_obligations_raw",
            return_value=[],
        ) as mock_query:
            repo.list_for_employee_no_join("co-1", "emp-1")
            mock_query.assert_called_once()
            assert mock_query.call_args[1]["with_employee_join"] is False


class TestMedicalObligationRepositoryEmployeeExists:
    """employee_exists."""

    def test_returns_true_when_found(self, repo: MedicalObligationRepository):
        """get_employee_by_id retourne une ligne → True."""
        with patch(
            "app.modules.medical_follow_up.infrastructure.repository.infra_queries.get_employee_by_id",
            return_value={"id": "emp-1", "company_id": "co-1"},
        ):
            assert repo.employee_exists("emp-1", "co-1") is True

    def test_returns_false_when_not_found(self, repo: MedicalObligationRepository):
        """get_employee_by_id retourne None → False."""
        with patch(
            "app.modules.medical_follow_up.infrastructure.repository.infra_queries.get_employee_by_id",
            return_value=None,
        ):
            assert repo.employee_exists("emp-unknown", "co-1") is False


class TestMedicalObligationRepositoryGetEmployeeIdByUserId:
    """get_employee_id_by_user_id."""

    def test_returns_employee_id_when_found(self, repo: MedicalObligationRepository):
        """Retourne l'id employé si trouvé."""
        with patch(
            "app.modules.medical_follow_up.infrastructure.repository.infra_queries.get_employee_id_by_user_id",
            return_value="emp-1",
        ) as mock_query:
            result = repo.get_employee_id_by_user_id("user-1", "co-1")
            mock_query.assert_called_once()
        assert result == "emp-1"

    def test_returns_none_when_not_found(self, repo: MedicalObligationRepository):
        """Retourne None si pas d'employé pour ce user/company."""
        with patch(
            "app.modules.medical_follow_up.infrastructure.repository.infra_queries.get_employee_id_by_user_id",
            return_value=None,
        ):
            result = repo.get_employee_id_by_user_id("user-unknown", "co-1")
        assert result is None
