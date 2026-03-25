"""
Tests unitaires des queries annual_reviews (application/queries.py).

Repository mocké ; pas de DB ni HTTP.
"""

from unittest.mock import MagicMock

import pytest

from app.modules.annual_reviews.application import queries


def _mock_repo():
    """Repository mock pour les tests."""
    return MagicMock()


class TestListAllAnnualReviews:
    """Query list_all_annual_reviews."""

    def test_returns_list_items_from_repository(self):
        """Retourne une liste de AnnualReviewListItem mappés depuis le repo."""
        repo = _mock_repo()
        repo.list_by_company.return_value = [
            {
                "id": "rev-1",
                "employee_id": "emp-1",
                "year": 2024,
                "status": "accepte",
                "planned_date": None,
                "completed_date": None,
                "created_at": "2024-01-01T00:00:00",
                "employees": {
                    "first_name": "Jean",
                    "last_name": "Dupont",
                    "job_title": "Dev",
                },
            },
        ]

        result = queries.list_all_annual_reviews("co-1", repository=repo)

        assert len(result) == 1
        assert result[0].id == "rev-1"
        assert result[0].employee_id == "emp-1"
        assert result[0].first_name == "Jean"
        assert result[0].last_name == "Dupont"
        assert result[0].job_title == "Dev"
        assert result[0].year == 2024
        assert result[0].status == "accepte"
        repo.list_by_company.assert_called_once_with("co-1", year=None, status=None)

    def test_passes_year_and_status_filters(self):
        """Transmet year et status au repository."""
        repo = _mock_repo()
        repo.list_by_company.return_value = []

        queries.list_all_annual_reviews(
            "co-1", repository=repo, year=2024, status="cloture"
        )

        repo.list_by_company.assert_called_once_with(
            "co-1", year=2024, status="cloture"
        )


class TestGetAnnualReviewById:
    """Query get_annual_review_by_id."""

    def test_returns_none_when_not_found(self):
        """Entretien inexistant → None."""
        repo = _mock_repo()
        repo.get_by_id.return_value = None
        assert (
            queries.get_annual_review_by_id(
                "rev-unknown", "co-1", "user-1", True, repository=repo
            )
            is None
        )

    def test_returns_none_when_other_company(self):
        """Entretien d'une autre entreprise → None."""
        repo = _mock_repo()
        repo.get_by_id.return_value = {
            "id": "rev-1",
            "company_id": "co-other",
            "employee_id": "emp-1",
        }
        assert (
            queries.get_annual_review_by_id(
                "rev-1", "co-1", "user-1", True, repository=repo
            )
            is None
        )

    def test_returns_none_when_employee_not_owner_and_not_rh(self):
        """Employé non propriétaire et pas RH → None."""
        repo = _mock_repo()
        repo.get_by_id.return_value = {
            "id": "rev-1",
            "company_id": "co-1",
            "employee_id": "emp-other",
            "year": 2024,
            "status": "accepte",
            "created_at": "2024-01-01T00:00:00",
            "updated_at": "2024-01-01T00:00:00",
        }
        assert (
            queries.get_annual_review_by_id(
                "rev-1", "co-1", "user-1", is_rh=False, repository=repo
            )
            is None
        )

    def test_returns_read_when_rh(self):
        """RH → retourne AnnualReviewRead."""
        repo = _mock_repo()
        row = {
            "id": "rev-1",
            "employee_id": "emp-1",
            "company_id": "co-1",
            "year": 2024,
            "status": "accepte",
            "created_at": "2024-01-01T00:00:00",
            "updated_at": "2024-01-01T00:00:00",
        }
        repo.get_by_id.return_value = row

        result = queries.get_annual_review_by_id(
            "rev-1", "co-1", "user-1", is_rh=True, repository=repo
        )

        assert result is not None
        assert result.id == "rev-1"
        assert result.employee_id == "emp-1"
        assert result.company_id == "co-1"
        assert result.year == 2024
        assert result.status == "accepte"

    def test_returns_read_when_employee_is_owner(self):
        """Employé propriétaire → retourne AnnualReviewRead."""
        repo = _mock_repo()
        row = {
            "id": "rev-1",
            "employee_id": "user-1",
            "company_id": "co-1",
            "year": 2024,
            "status": "accepte",
            "created_at": "2024-01-01T00:00:00",
            "updated_at": "2024-01-01T00:00:00",
        }
        repo.get_by_id.return_value = row

        result = queries.get_annual_review_by_id(
            "rev-1", "co-1", "user-1", is_rh=False, repository=repo
        )

        assert result is not None
        assert result.employee_id == "user-1"


class TestListEmployeeAnnualReviews:
    """Query list_employee_annual_reviews."""

    def test_raises_lookup_error_when_employee_not_in_company(self):
        """Employé non trouvé ou autre entreprise → LookupError."""
        repo = _mock_repo()
        repo.get_employee_company_id.return_value = None
        with pytest.raises(LookupError):
            queries.list_employee_annual_reviews("emp-1", "co-1", repository=repo)

        repo.get_employee_company_id.return_value = "co-other"
        with pytest.raises(LookupError):
            queries.list_employee_annual_reviews("emp-1", "co-1", repository=repo)

    def test_returns_list_of_reads(self):
        """Retourne liste de AnnualReviewRead pour l'employé."""
        repo = _mock_repo()
        repo.get_employee_company_id.return_value = "co-1"
        repo.list_by_employee.return_value = [
            {
                "id": "rev-1",
                "employee_id": "emp-1",
                "company_id": "co-1",
                "year": 2024,
                "status": "cloture",
                "created_at": "2024-01-01T00:00:00",
                "updated_at": "2024-06-20T00:00:00",
            },
        ]

        result = queries.list_employee_annual_reviews("emp-1", "co-1", repository=repo)

        assert len(result) == 1
        assert result[0].id == "rev-1"
        assert result[0].employee_id == "emp-1"
        repo.list_by_employee.assert_called_once_with("emp-1", "co-1")


class TestGetMyAnnualReviews:
    """Query get_my_annual_reviews."""

    def test_returns_list_from_list_by_employee(self):
        """Retourne les entretiens de l'employé connecté."""
        repo = _mock_repo()
        repo.list_by_employee.return_value = [
            {
                "id": "rev-1",
                "employee_id": "user-1",
                "company_id": "co-1",
                "year": 2024,
                "status": "accepte",
                "created_at": "2024-01-01T00:00:00",
                "updated_at": "2024-01-01T00:00:00",
            },
        ]

        result = queries.get_my_annual_reviews("user-1", "co-1", repository=repo)

        assert len(result) == 1
        assert result[0].employee_id == "user-1"
        repo.list_by_employee.assert_called_once_with("user-1", "co-1")


class TestGetMyCurrentAnnualReview:
    """Query get_my_current_annual_review."""

    def test_returns_none_when_no_current(self):
        """Pas d'entretien pour l'année → None."""
        repo = _mock_repo()
        repo.get_my_current.return_value = None

        result = queries.get_my_current_annual_review(
            "user-1", "co-1", 2024, repository=repo
        )

        assert result is None
        repo.get_my_current.assert_called_once_with("user-1", "co-1", 2024)

    def test_returns_read_when_found(self):
        """Entretien trouvé → AnnualReviewRead."""
        repo = _mock_repo()
        row = {
            "id": "rev-1",
            "employee_id": "user-1",
            "company_id": "co-1",
            "year": 2024,
            "status": "en_attente_acceptation",
            "created_at": "2024-01-01T00:00:00",
            "updated_at": "2024-01-01T00:00:00",
        }
        repo.get_my_current.return_value = row

        result = queries.get_my_current_annual_review(
            "user-1", "co-1", 2024, repository=repo
        )

        assert result is not None
        assert result.year == 2024
        assert result.status == "en_attente_acceptation"


class TestGetAnnualReviewForPdf:
    """Query get_annual_review_for_pdf."""

    def test_returns_none_when_not_found(self):
        """Entretien inexistant → None."""
        repo = _mock_repo()
        repo.get_by_id.return_value = None
        assert (
            queries.get_annual_review_for_pdf(
                "rev-unknown", "co-1", "user-1", True, repository=repo
            )
            is None
        )

    def test_returns_none_when_other_company(self):
        """Autre entreprise → None."""
        repo = _mock_repo()
        repo.get_by_id.return_value = {
            "id": "rev-1",
            "company_id": "co-other",
            "employee_id": "emp-1",
        }
        assert (
            queries.get_annual_review_for_pdf(
                "rev-1", "co-1", "user-1", True, repository=repo
            )
            is None
        )

    def test_returns_none_when_employee_not_owner_and_not_rh(self):
        """Employé non propriétaire et pas RH → None."""
        repo = _mock_repo()
        repo.get_by_id.return_value = {
            "id": "rev-1",
            "company_id": "co-1",
            "employee_id": "emp-other",
            "status": "cloture",
        }
        assert (
            queries.get_annual_review_for_pdf(
                "rev-1", "co-1", "user-1", is_rh=False, repository=repo
            )
            is None
        )

    def test_raises_value_error_when_status_not_cloture(self):
        """Statut != cloture → ValueError (PDF non autorisé)."""
        repo = _mock_repo()
        repo.get_by_id.return_value = {
            "id": "rev-1",
            "company_id": "co-1",
            "employee_id": "user-1",
            "status": "realise",
        }
        with pytest.raises(ValueError) as exc_info:
            queries.get_annual_review_for_pdf(
                "rev-1", "co-1", "user-1", is_rh=True, repository=repo
            )
        assert "clôturé" in str(exc_info.value) or "PDF" in str(exc_info.value)

    def test_returns_row_when_cloture_and_authorized(self):
        """Statut cloture et accès OK → dict row pour le PDF."""
        repo = _mock_repo()
        row = {
            "id": "rev-1",
            "company_id": "co-1",
            "employee_id": "emp-1",
            "year": 2024,
            "status": "cloture",
        }
        repo.get_by_id.return_value = row

        result = queries.get_annual_review_for_pdf(
            "rev-1", "co-1", "user-1", is_rh=True, repository=repo
        )

        assert result == row
