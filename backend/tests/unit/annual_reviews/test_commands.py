"""
Tests unitaires des commandes annual_reviews (application/commands.py).

Repository mocké ; pas de DB ni HTTP.
"""
from datetime import date
from unittest.mock import MagicMock

import pytest

from app.modules.annual_reviews.application import commands


def _mock_repo():
    """Repository mock pour les tests."""
    return MagicMock()


class TestCreateAnnualReview:
    """Commande create_annual_review."""

    def test_raises_value_error_when_employee_id_missing(self):
        """employee_id manquant → ValueError."""
        repo = _mock_repo()
        with pytest.raises(ValueError) as exc_info:
            commands.create_annual_review(
                company_id="co-1",
                data={"year": 2024},
                repository=repo,
            )
        assert "employee_id" in str(exc_info.value).lower() or "requis" in str(exc_info.value)
        repo.get_employee_company_id.assert_not_called()

    def test_raises_lookup_error_when_employee_not_found(self):
        """Employé non trouvé ou autre entreprise → LookupError."""
        repo = _mock_repo()
        repo.get_employee_company_id.return_value = None
        with pytest.raises(LookupError) as exc_info:
            commands.create_annual_review(
                company_id="co-1",
                data={"employee_id": "emp-1", "year": 2024},
                repository=repo,
            )
        assert "Employé" in str(exc_info.value) or "trouvé" in str(exc_info.value).lower()
        repo.get_employee_company_id.assert_called_once_with("emp-1")

    def test_raises_lookup_error_when_employee_in_other_company(self):
        """Employé d'une autre entreprise → LookupError."""
        repo = _mock_repo()
        repo.get_employee_company_id.return_value = "co-other"
        with pytest.raises(LookupError):
            commands.create_annual_review(
                company_id="co-1",
                data={"employee_id": "emp-1", "year": 2024},
                repository=repo,
            )

    def test_creates_with_default_status_and_returns_row(self):
        """Crée avec statut en_attente_acceptation et retourne la ligne."""
        repo = _mock_repo()
        repo.get_employee_company_id.return_value = "co-1"
        created_row = {
            "id": "rev-new",
            "employee_id": "emp-1",
            "company_id": "co-1",
            "year": 2024,
            "status": "en_attente_acceptation",
            "planned_date": None,
            "created_at": "2024-01-01T00:00:00",
            "updated_at": "2024-01-01T00:00:00",
        }
        repo.create.return_value = created_row

        result = commands.create_annual_review(
            company_id="co-1",
            data={"employee_id": "emp-1", "year": 2024},
            repository=repo,
        )

        assert result == created_row
        repo.create.assert_called_once()
        call_data = repo.create.call_args[0][0]
        assert call_data["employee_id"] == "emp-1"
        assert call_data["company_id"] == "co-1"
        assert call_data["year"] == 2024
        assert call_data["status"] == "en_attente_acceptation"
        assert call_data.get("planned_date") is None

    def test_creates_with_planned_date_and_rh_template(self):
        """Crée avec planned_date et rh_preparation_template si fournis."""
        repo = _mock_repo()
        repo.get_employee_company_id.return_value = "co-1"
        planned = date(2024, 6, 15)
        repo.create.return_value = {"id": "rev-1"}

        commands.create_annual_review(
            company_id="co-1",
            data={
                "employee_id": "emp-1",
                "year": 2024,
                "planned_date": planned,
                "rh_preparation_template": "Template",
            },
            repository=repo,
        )

        call_data = repo.create.call_args[0][0]
        assert call_data["planned_date"] == "2024-06-15"
        assert call_data["rh_preparation_template"] == "Template"


class TestUpdateAnnualReview:
    """Commande update_annual_review."""

    def test_raises_lookup_error_when_review_not_found(self):
        """Entretien inexistant → LookupError."""
        repo = _mock_repo()
        repo.get_by_id.return_value = None
        with pytest.raises(LookupError):
            commands.update_annual_review(
                review_id="rev-unknown",
                company_id="co-1",
                current_user_id="user-1",
                is_rh=True,
                data={"status": "accepte"},
                repository=repo,
            )

    def test_raises_lookup_error_when_review_other_company(self):
        """Entretien d'une autre entreprise → LookupError."""
        repo = _mock_repo()
        repo.get_by_id.return_value = {
            "id": "rev-1",
            "company_id": "co-other",
            "employee_id": "emp-1",
            "status": "accepte",
        }
        with pytest.raises(LookupError):
            commands.update_annual_review(
                review_id="rev-1",
                company_id="co-1",
                current_user_id="user-1",
                is_rh=True,
                data={},
                repository=repo,
            )

    def test_raises_permission_error_when_employee_updates_other_review(self):
        """Employé tente de modifier l'entretien d'un autre → PermissionError."""
        repo = _mock_repo()
        repo.get_by_id.return_value = {
            "id": "rev-1",
            "company_id": "co-1",
            "employee_id": "emp-other",
            "status": "en_attente_acceptation",
        }
        with pytest.raises(PermissionError):
            commands.update_annual_review(
                review_id="rev-1",
                company_id="co-1",
                current_user_id="user-1",
                is_rh=False,
                data={"employee_acceptance_status": "accepte"},
                repository=repo,
            )

    def test_employee_acceptance_sets_status_and_date(self):
        """Employé accepte : status=accepte et employee_acceptance_date renseigné."""
        repo = _mock_repo()
        repo.get_by_id.return_value = {
            "id": "rev-1",
            "company_id": "co-1",
            "employee_id": "user-1",
            "status": "en_attente_acceptation",
        }
        updated = {
            "id": "rev-1",
            "status": "accepte",
            "employee_acceptance_date": "2024-01-15T10:00:00",
            "created_at": "2024-01-01T00:00:00",
            "updated_at": "2024-01-15T10:00:00",
        }
        repo.update.return_value = updated

        result = commands.update_annual_review(
            review_id="rev-1",
            company_id="co-1",
            current_user_id="user-1",
            is_rh=False,
            data={"employee_acceptance_status": "accepte"},
            repository=repo,
        )

        assert result == updated
        repo.update.assert_called_once()
        call_data = repo.update.call_args[0][1]
        assert call_data["employee_acceptance_status"] == "accepte"
        assert call_data["status"] == "accepte"
        assert "employee_acceptance_date" in call_data

    def test_rh_update_serializes_dates(self):
        """RH met à jour : planned_date/completed_date sérialisées en ISO."""
        repo = _mock_repo()
        repo.get_by_id.return_value = {
            "id": "rev-1",
            "company_id": "co-1",
            "employee_id": "emp-1",
            "status": "realise",
        }
        repo.update.return_value = {"id": "rev-1", "planned_date": "2024-06-15"}

        commands.update_annual_review(
            review_id="rev-1",
            company_id="co-1",
            current_user_id="rh-1",
            is_rh=True,
            data={"planned_date": date(2024, 6, 15), "meeting_report": "CR"},
            repository=repo,
        )

        call_data = repo.update.call_args[0][1]
        assert call_data["planned_date"] == "2024-06-15"
        assert call_data["meeting_report"] == "CR"

    def test_returns_row_when_update_returns_none(self):
        """Si update retourne None, la commande retourne la row initiale."""
        repo = _mock_repo()
        row = {"id": "rev-1", "company_id": "co-1", "employee_id": "emp-1", "status": "accepte"}
        repo.get_by_id.return_value = row
        repo.update.return_value = None

        result = commands.update_annual_review(
            review_id="rev-1",
            company_id="co-1",
            current_user_id="rh-1",
            is_rh=True,
            data={},
            repository=repo,
        )

        assert result == row


class TestMarkCompleted:
    """Commande mark_completed."""

    def test_raises_lookup_error_when_review_not_found(self):
        """Entretien non trouvé → LookupError."""
        repo = _mock_repo()
        repo.get_by_id.return_value = None
        with pytest.raises(LookupError):
            commands.mark_completed("rev-unknown", "co-1", repository=repo)

    def test_raises_lookup_error_when_other_company(self):
        """Entretien autre entreprise → LookupError."""
        repo = _mock_repo()
        repo.get_by_id.return_value = {"id": "rev-1", "company_id": "co-other", "status": "accepte"}
        with pytest.raises(LookupError):
            commands.mark_completed("rev-1", "co-1", repository=repo)

    def test_raises_value_error_when_status_not_accepte(self):
        """Statut != accepte → ValueError (règle métier)."""
        repo = _mock_repo()
        repo.get_by_id.return_value = {
            "id": "rev-1",
            "company_id": "co-1",
            "status": "en_attente_acceptation",
        }
        with pytest.raises(ValueError) as exc_info:
            commands.mark_completed("rev-1", "co-1", repository=repo)
        assert "accepté" in str(exc_info.value) or "réalisé" in str(exc_info.value).lower()

    def test_updates_to_realise_with_completed_date(self):
        """Statut accepte → realise et completed_date = today."""
        repo = _mock_repo()
        repo.get_by_id.return_value = {
            "id": "rev-1",
            "company_id": "co-1",
            "status": "accepte",
        }
        updated = {
            "id": "rev-1",
            "status": "realise",
            "completed_date": date.today().isoformat(),
            "created_at": "2024-01-01T00:00:00",
            "updated_at": "2024-01-15T10:00:00",
        }
        repo.update.return_value = updated

        result = commands.mark_completed("rev-1", "co-1", repository=repo)

        assert result == updated
        repo.update.assert_called_once()
        call_data = repo.update.call_args[0][1]
        assert call_data["status"] == "realise"
        assert "completed_date" in call_data

    def test_raises_runtime_error_when_updated_missing_created_updated_at(self):
        """Si update ne renvoie pas created_at/updated_at → RuntimeError."""
        repo = _mock_repo()
        repo.get_by_id.return_value = {"id": "rev-1", "company_id": "co-1", "status": "accepte"}
        repo.update.return_value = {"id": "rev-1", "status": "realise"}
        with pytest.raises(RuntimeError) as exc_info:
            commands.mark_completed("rev-1", "co-1", repository=repo)
        assert "created_at" in str(exc_info.value) or "updated_at" in str(exc_info.value)


class TestDeleteAnnualReview:
    """Commande delete_annual_review."""

    def test_raises_lookup_error_when_review_not_found(self):
        """Entretien non trouvé → LookupError."""
        repo = _mock_repo()
        repo.get_by_id.return_value = None
        with pytest.raises(LookupError):
            commands.delete_annual_review("rev-unknown", "co-1", repository=repo)

    def test_raises_lookup_error_when_other_company(self):
        """Entretien autre entreprise → LookupError."""
        repo = _mock_repo()
        repo.get_by_id.return_value = {"id": "rev-1", "company_id": "co-other"}
        with pytest.raises(LookupError):
            commands.delete_annual_review("rev-1", "co-1", repository=repo)

    def test_calls_repository_delete(self):
        """Appelle repository.delete avec le bon id."""
        repo = _mock_repo()
        repo.get_by_id.return_value = {"id": "rev-1", "company_id": "co-1"}

        commands.delete_annual_review("rev-1", "co-1", repository=repo)

        repo.delete.assert_called_once_with("rev-1")
