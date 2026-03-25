"""
Tests unitaires des commandes medical_follow_up (application/commands.py).

Repository mocké via get_obligation_repository ; pas de DB ni HTTP.
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.modules.medical_follow_up.application import commands
from app.modules.medical_follow_up.schemas.requests import (
    CreateOnDemandBody,
    MarkCompletedBody,
    MarkPlanifiedBody,
)


def _mock_repo():
    """Repository mock pour les tests."""
    repo = MagicMock()
    repo.obligation_exists.return_value = True
    repo.employee_exists.return_value = True
    repo.mark_planified.return_value = None
    repo.mark_completed.return_value = None
    repo.create_on_demand.return_value = None
    return repo


@patch("app.modules.medical_follow_up.application.commands.get_obligation_repository")
class TestMarkPlanified:
    """Commande mark_planified."""

    def test_returns_ok_when_obligation_exists(self, mock_get_repo):
        """Obligation trouvée → appelle mark_planified et retourne {"ok": True}."""
        repo = _mock_repo()
        mock_get_repo.return_value = repo
        body = MarkPlanifiedBody(planned_date="2025-04-15", justification="RDV fixé")
        result = commands.mark_planified(
            "obl-1", body, "co-1", current_user=MagicMock()
        )
        assert result == {"ok": True}
        repo.obligation_exists.assert_called_once_with("obl-1", "co-1")
        repo.mark_planified.assert_called_once_with(
            "obl-1", "co-1", "2025-04-15", "RDV fixé"
        )

    def test_raises_404_when_obligation_not_found(self, mock_get_repo):
        """Obligation inexistante → HTTPException 404."""
        repo = _mock_repo()
        repo.obligation_exists.return_value = False
        mock_get_repo.return_value = repo
        body = MarkPlanifiedBody(planned_date="2025-04-15")
        with pytest.raises(HTTPException) as exc_info:
            commands.mark_planified(
                "obl-unknown", body, "co-1", current_user=MagicMock()
            )
        assert exc_info.value.status_code == 404
        assert (
            "Obligation" in exc_info.value.detail or "trouvée" in exc_info.value.detail
        )
        repo.mark_planified.assert_not_called()

    def test_justification_optional(self, mock_get_repo):
        """justification peut être omise (None)."""
        repo = _mock_repo()
        mock_get_repo.return_value = repo
        body = MarkPlanifiedBody(planned_date="2025-04-15")
        commands.mark_planified("obl-1", body, "co-1", current_user=MagicMock())
        repo.mark_planified.assert_called_once_with("obl-1", "co-1", "2025-04-15", None)


@patch("app.modules.medical_follow_up.application.commands.get_obligation_repository")
class TestMarkCompleted:
    """Commande mark_completed."""

    def test_returns_ok_when_obligation_exists(self, mock_get_repo):
        """Obligation trouvée → appelle mark_completed et retourne {"ok": True}."""
        repo = _mock_repo()
        mock_get_repo.return_value = repo
        body = MarkCompletedBody(
            completed_date="2025-04-20", justification="Visite effectuée"
        )
        result = commands.mark_completed(
            "obl-1", body, "co-1", current_user=MagicMock()
        )
        assert result == {"ok": True}
        repo.obligation_exists.assert_called_once_with("obl-1", "co-1")
        repo.mark_completed.assert_called_once_with(
            "obl-1", "co-1", "2025-04-20", "Visite effectuée"
        )

    def test_raises_404_when_obligation_not_found(self, mock_get_repo):
        """Obligation inexistante → HTTPException 404."""
        repo = _mock_repo()
        repo.obligation_exists.return_value = False
        mock_get_repo.return_value = repo
        body = MarkCompletedBody(completed_date="2025-04-20")
        with pytest.raises(HTTPException) as exc_info:
            commands.mark_completed(
                "obl-unknown", body, "co-1", current_user=MagicMock()
            )
        assert exc_info.value.status_code == 404
        repo.mark_completed.assert_not_called()


@patch("app.modules.medical_follow_up.application.commands.get_obligation_repository")
class TestCreateOnDemand:
    """Commande create_on_demand."""

    def test_returns_ok_when_employee_exists(self, mock_get_repo):
        """Salarié trouvé → appelle create_on_demand et retourne {"ok": True}."""
        repo = _mock_repo()
        mock_get_repo.return_value = repo
        body = CreateOnDemandBody(
            employee_id="emp-1",
            request_motif="Demande du salarié",
            request_date="2025-03-17",
        )
        result = commands.create_on_demand(body, "co-1", current_user=MagicMock())
        assert result == {"ok": True}
        repo.employee_exists.assert_called_once_with("emp-1", "co-1")
        repo.create_on_demand.assert_called_once_with(
            "co-1", "emp-1", "Demande du salarié", "2025-03-17"
        )

    def test_raises_404_when_employee_not_found(self, mock_get_repo):
        """Salarié inexistant → HTTPException 404."""
        repo = _mock_repo()
        repo.employee_exists.return_value = False
        mock_get_repo.return_value = repo
        body = CreateOnDemandBody(
            employee_id="emp-unknown",
            request_motif="Motif",
            request_date="2025-03-17",
        )
        with pytest.raises(HTTPException) as exc_info:
            commands.create_on_demand(body, "co-1", current_user=MagicMock())
        assert exc_info.value.status_code == 404
        assert "Salarié" in exc_info.value.detail or "trouvé" in exc_info.value.detail
        repo.create_on_demand.assert_not_called()
