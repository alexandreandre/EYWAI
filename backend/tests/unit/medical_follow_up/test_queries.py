"""
Tests unitaires des queries medical_follow_up (application/queries.py).

Repository et service (compute_obligations, get_company_medical_setting) mockés ; pas de DB ni HTTP.
"""
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.modules.medical_follow_up.application import queries
from app.modules.medical_follow_up.application.dto import KPIsDTO, ObligationListDTO


def _mock_repo():
    """Repository mock pour les tests."""
    repo = MagicMock()
    repo.list_for_company.return_value = []
    repo.get_kpis.return_value = {
        "overdue_count": 0,
        "due_within_30_count": 0,
        "active_total": 0,
        "completed_this_month": 0,
    }
    repo.employee_exists.return_value = True
    repo.get_employee_id_by_user_id.return_value = "emp-1"
    repo.list_for_employee.return_value = []
    repo.list_for_employee_no_join.return_value = []
    return repo


@patch("app.modules.medical_follow_up.application.queries.get_obligation_repository")
class TestListObligations:
    """Query list_obligations."""

    def test_returns_list_of_dtos(self, mock_get_repo):
        """Délègue au repo et retourne une liste d'ObligationListDTO."""
        repo = _mock_repo()
        repo.list_for_company.return_value = [
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
        mock_get_repo.return_value = repo
        result = queries.list_obligations("co-1", MagicMock())
        assert len(result) == 1
        assert isinstance(result[0], ObligationListDTO)
        assert result[0].id == "obl-1"
        assert result[0].visit_type == "vip"
        repo.list_for_company.assert_called_once_with("co-1", employee_id=None, visit_type=None, status=None, priority=None, due_from=None, due_to=None)

    def test_passes_filters_to_repo(self, mock_get_repo):
        """Transmet employee_id, visit_type, status, etc. au repo."""
        repo = _mock_repo()
        mock_get_repo.return_value = repo
        queries.list_obligations(
            "co-1",
            MagicMock(),
            employee_id="emp-1",
            visit_type="vip",
            status="a_faire",
            priority=1,
            due_from="2025-01-01",
            due_to="2025-12-31",
        )
        repo.list_for_company.assert_called_once_with(
            "co-1",
            employee_id="emp-1",
            visit_type="vip",
            status="a_faire",
            priority=1,
            due_from="2025-01-01",
            due_to="2025-12-31",
        )


@patch("app.modules.medical_follow_up.application.queries.get_obligation_repository")
class TestGetKpis:
    """Query get_kpis."""

    def test_returns_kpis_dto(self, mock_get_repo):
        """Retourne KPIsDTO avec les valeurs du repo."""
        repo = _mock_repo()
        repo.get_kpis.return_value = {
            "overdue_count": 2,
            "due_within_30_count": 3,
            "active_total": 5,
            "completed_this_month": 1,
        }
        mock_get_repo.return_value = repo
        result = queries.get_kpis("co-1", MagicMock())
        assert isinstance(result, KPIsDTO)
        assert result.overdue_count == 2
        assert result.due_within_30_count == 3
        assert result.active_total == 5
        assert result.completed_this_month == 1
        repo.get_kpis.assert_called_once_with("co-1")


@patch("app.modules.medical_follow_up.application.queries.compute_obligations_for_employee")
@patch("app.modules.medical_follow_up.application.queries.get_obligation_repository")
class TestListObligationsForEmployee:
    """Query list_obligations_for_employee."""

    def test_raises_404_when_employee_not_found(self, mock_get_repo, mock_compute):
        """Salarié inexistant → HTTPException 404."""
        repo = _mock_repo()
        repo.employee_exists.return_value = False
        mock_get_repo.return_value = repo
        with pytest.raises(HTTPException) as exc_info:
            queries.list_obligations_for_employee("co-1", "emp-unknown", MagicMock())
        assert exc_info.value.status_code == 404
        mock_compute.assert_not_called()

    def test_calls_compute_then_returns_list(self, mock_get_repo, mock_compute):
        """Employé trouvé → compute_obligations_for_employee puis list_for_employee."""
        repo = _mock_repo()
        repo.list_for_employee.return_value = [
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
        mock_get_repo.return_value = repo
        result = queries.list_obligations_for_employee("co-1", "emp-1", MagicMock())
        mock_compute.assert_called_once_with("co-1", "emp-1")
        assert len(result) == 1
        assert result[0].id == "obl-1"


@patch("app.modules.medical_follow_up.application.queries.compute_obligations_for_employee")
@patch("app.modules.medical_follow_up.application.queries.get_obligation_repository")
class TestMyObligations:
    """Query my_obligations (obligations du collaborateur connecté)."""

    def test_raises_404_when_no_employee_for_user(self, mock_get_repo, mock_compute):
        """Pas d'employé associé au user → HTTPException 404."""
        repo = _mock_repo()
        repo.get_employee_id_by_user_id.return_value = None
        mock_get_repo.return_value = repo
        user = MagicMock()
        user.id = "user-1"
        with pytest.raises(HTTPException) as exc_info:
            queries.my_obligations("co-1", user)
        assert exc_info.value.status_code == 404
        assert "Profil" in exc_info.value.detail or "trouvé" in exc_info.value.detail

    def test_returns_list_when_employee_found(self, mock_get_repo, mock_compute):
        """Employé trouvé → compute puis list_for_employee_no_join."""
        repo = _mock_repo()
        repo.list_for_employee_no_join.return_value = [
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
        mock_get_repo.return_value = repo
        user = MagicMock()
        user.id = "user-1"
        result = queries.my_obligations("co-1", user)
        repo.get_employee_id_by_user_id.assert_called_once_with("user-1", "co-1")
        mock_compute.assert_called_once_with("co-1", "emp-1")
        assert len(result) == 1
        assert result[0].id == "obl-1"


@patch("app.modules.medical_follow_up.application.queries.get_company_medical_setting")
class TestGetMedicalSettings:
    """Query get_medical_settings."""

    def test_returns_enabled_false_when_no_company(self, mock_get_setting):
        """company_id None → {"enabled": False}."""
        result = queries.get_medical_settings(None, MagicMock())
        assert result == {"enabled": False}
        mock_get_setting.assert_not_called()

    def test_returns_enabled_from_provider(self, mock_get_setting):
        """company_id fourni → {"enabled": bool} selon le provider."""
        mock_get_setting.return_value = True
        result = queries.get_medical_settings("co-1", MagicMock())
        assert result == {"enabled": True}
        mock_get_setting.assert_called_once_with("co-1")

        mock_get_setting.return_value = False
        result = queries.get_medical_settings("co-2", MagicMock())
        assert result == {"enabled": False}


@patch("app.modules.medical_follow_up.application.queries.my_obligations")
@patch("app.modules.medical_follow_up.application.queries.get_company_medical_setting")
@patch("app.modules.medical_follow_up.application.queries.resolve_company_id_for_medical")
class TestGetMyObligationsWithGuards:
    """Query get_my_obligations_with_guards (route /me avec gardes)."""

    def test_raises_400_when_no_company(self, mock_resolve, mock_setting, mock_my_obligations):
        """Pas d'entreprise active → HTTPException 400."""
        mock_resolve.return_value = None
        with pytest.raises(HTTPException) as exc_info:
            queries.get_my_obligations_with_guards(MagicMock())
        assert exc_info.value.status_code == 400
        assert "entreprise" in exc_info.value.detail.lower()
        mock_setting.assert_not_called()
        mock_my_obligations.assert_not_called()

    def test_raises_403_when_module_disabled(self, mock_resolve, mock_setting, mock_my_obligations):
        """Module désactivé → HTTPException 403."""
        mock_resolve.return_value = "co-1"
        mock_setting.return_value = False
        with pytest.raises(HTTPException) as exc_info:
            queries.get_my_obligations_with_guards(MagicMock())
        assert exc_info.value.status_code == 403
        assert "suivi médical" in exc_info.value.detail.lower() or "non activé" in exc_info.value.detail
        mock_my_obligations.assert_not_called()

    def test_returns_my_obligations_when_ok(self, mock_resolve, mock_setting, mock_my_obligations):
        """Entreprise active et module activé → appelle my_obligations et retourne la liste."""
        mock_resolve.return_value = "co-1"
        mock_setting.return_value = True
        user = MagicMock()
        mock_my_obligations.return_value = [
            ObligationListDTO(
                id="obl-1",
                company_id="co-1",
                employee_id="emp-1",
                visit_type="vip",
                trigger_type="periodicite_vip",
                due_date="2025-06-01",
                priority=1,
                status="a_faire",
                rule_source="legal",
            ),
        ]
        result = queries.get_my_obligations_with_guards(user)
        mock_my_obligations.assert_called_once_with("co-1", user)
        assert len(result) == 1
        assert result[0].id == "obl-1"
