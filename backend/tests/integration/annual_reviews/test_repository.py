"""
Tests d'intégration du repository annual_reviews (SupabaseAnnualReviewRepository).

Vérifie que le repository délègue correctement aux requêtes infrastructure
et retourne les données attendues. Les requêtes DB sont mockées (pas de DB réelle).
Pour des tests contre une DB de test, prévoir db_session et données dans annual_reviews/employees/companies.
"""
from unittest.mock import patch, MagicMock

import pytest

from app.modules.annual_reviews.infrastructure.repository import SupabaseAnnualReviewRepository


pytestmark = pytest.mark.integration


@pytest.fixture
def repo():
    """Instance du repository à tester."""
    return SupabaseAnnualReviewRepository()


class TestSupabaseAnnualReviewRepositoryListByCompany:
    """list_by_company."""

    def test_calls_query_with_company_id(self, repo: SupabaseAnnualReviewRepository):
        """Délègue à query_list_by_company avec company_id."""
        with patch(
            "app.modules.annual_reviews.infrastructure.repository.infra_queries.query_list_by_company",
            return_value=[],
        ) as mock_query:
            repo.list_by_company("co-1")
            mock_query.assert_called_once_with("co-1", year=None, status=None)

    def test_calls_query_with_year_and_status(self, repo: SupabaseAnnualReviewRepository):
        """Transmet year et status aux filtres."""
        with patch(
            "app.modules.annual_reviews.infrastructure.repository.infra_queries.query_list_by_company",
            return_value=[],
        ) as mock_query:
            repo.list_by_company("co-1", year=2024, status="cloture")
            mock_query.assert_called_once_with("co-1", year=2024, status="cloture")

    def test_returns_data_from_query(self, repo: SupabaseAnnualReviewRepository):
        """Retourne la liste renvoyée par la requête."""
        data = [
            {
                "id": "rev-1",
                "employee_id": "emp-1",
                "company_id": "co-1",
                "year": 2024,
                "status": "accepte",
                "employees": {"first_name": "Jean", "last_name": "Dupont"},
            },
        ]
        with patch(
            "app.modules.annual_reviews.infrastructure.repository.infra_queries.query_list_by_company",
            return_value=data,
        ):
            result = repo.list_by_company("co-1")
        assert result == data
        assert len(result) == 1
        assert result[0]["id"] == "rev-1"


class TestSupabaseAnnualReviewRepositoryGetById:
    """get_by_id."""

    def test_calls_query_with_review_id(self, repo: SupabaseAnnualReviewRepository):
        """Délègue à query_get_by_id."""
        with patch(
            "app.modules.annual_reviews.infrastructure.repository.infra_queries.query_get_by_id",
            return_value=None,
        ) as mock_query:
            repo.get_by_id("rev-1")
            mock_query.assert_called_once_with("rev-1")

    def test_returns_row_or_none(self, repo: SupabaseAnnualReviewRepository):
        """Retourne la ligne ou None."""
        row = {"id": "rev-1", "employee_id": "emp-1", "company_id": "co-1", "year": 2024, "status": "accepte"}
        with patch(
            "app.modules.annual_reviews.infrastructure.repository.infra_queries.query_get_by_id",
            return_value=row,
        ):
            result = repo.get_by_id("rev-1")
        assert result == row

        with patch(
            "app.modules.annual_reviews.infrastructure.repository.infra_queries.query_get_by_id",
            return_value=None,
        ):
            result = repo.get_by_id("rev-unknown")
        assert result is None


class TestSupabaseAnnualReviewRepositoryListByEmployee:
    """list_by_employee."""

    def test_calls_query_with_employee_and_company(self, repo: SupabaseAnnualReviewRepository):
        """Délègue à query_list_by_employee(employee_id, company_id)."""
        with patch(
            "app.modules.annual_reviews.infrastructure.repository.infra_queries.query_list_by_employee",
            return_value=[],
        ) as mock_query:
            repo.list_by_employee("emp-1", "co-1")
            mock_query.assert_called_once_with("emp-1", "co-1")

    def test_returns_list_from_query(self, repo: SupabaseAnnualReviewRepository):
        """Retourne la liste des entretiens de l'employé."""
        data = [{"id": "rev-1", "employee_id": "emp-1", "company_id": "co-1", "year": 2024}]
        with patch(
            "app.modules.annual_reviews.infrastructure.repository.infra_queries.query_list_by_employee",
            return_value=data,
        ):
            result = repo.list_by_employee("emp-1", "co-1")
        assert result == data


class TestSupabaseAnnualReviewRepositoryGetMyCurrent:
    """get_my_current."""

    def test_calls_query_with_employee_company_year(self, repo: SupabaseAnnualReviewRepository):
        """Délègue à query_get_my_current(employee_id, company_id, year)."""
        with patch(
            "app.modules.annual_reviews.infrastructure.repository.infra_queries.query_get_my_current",
            return_value=None,
        ) as mock_query:
            repo.get_my_current("emp-1", "co-1", 2024)
            mock_query.assert_called_once_with("emp-1", "co-1", 2024)

    def test_returns_row_or_none(self, repo: SupabaseAnnualReviewRepository):
        """Retourne l'entretien de l'année ou None."""
        row = {"id": "rev-1", "employee_id": "emp-1", "company_id": "co-1", "year": 2024}
        with patch(
            "app.modules.annual_reviews.infrastructure.repository.infra_queries.query_get_my_current",
            return_value=row,
        ):
            result = repo.get_my_current("emp-1", "co-1", 2024)
        assert result == row


class TestSupabaseAnnualReviewRepositoryCreate:
    """create."""

    def test_calls_query_insert_with_data(self, repo: SupabaseAnnualReviewRepository):
        """Délègue à query_insert et retourne la ligne créée."""
        insert_data = {
            "employee_id": "emp-1",
            "company_id": "co-1",
            "year": 2024,
            "status": "en_attente_acceptation",
        }
        created = {**insert_data, "id": "rev-new", "created_at": "2024-01-01T00:00:00", "updated_at": "2024-01-01T00:00:00"}
        with patch(
            "app.modules.annual_reviews.infrastructure.repository.infra_queries.query_insert",
            return_value=created,
        ) as mock_insert:
            result = repo.create(insert_data)
            mock_insert.assert_called_once_with(insert_data)
        assert result == created
        assert result["id"] == "rev-new"


class TestSupabaseAnnualReviewRepositoryUpdate:
    """update."""

    def test_calls_query_update_and_returns_updated_row(self, repo: SupabaseAnnualReviewRepository):
        """Délègue à query_update(review_id, data)."""
        update_data = {"status": "realise", "completed_date": "2024-06-15"}
        updated = {"id": "rev-1", "status": "realise", "completed_date": "2024-06-15"}
        with patch(
            "app.modules.annual_reviews.infrastructure.repository.infra_queries.query_update",
            return_value=updated,
        ) as mock_update:
            result = repo.update("rev-1", update_data)
            mock_update.assert_called_once_with("rev-1", update_data)
        assert result == updated

    def test_returns_none_when_query_returns_none(self, repo: SupabaseAnnualReviewRepository):
        """Si la requête ne renvoie pas de ligne, retourne None."""
        with patch(
            "app.modules.annual_reviews.infrastructure.repository.infra_queries.query_update",
            return_value=None,
        ):
            result = repo.update("rev-1", {"status": "cloture"})
        assert result is None


class TestSupabaseAnnualReviewRepositoryDelete:
    """delete."""

    def test_calls_query_delete(self, repo: SupabaseAnnualReviewRepository):
        """Délègue à query_delete(review_id)."""
        with patch(
            "app.modules.annual_reviews.infrastructure.repository.infra_queries.query_delete",
        ) as mock_delete:
            repo.delete("rev-1")
            mock_delete.assert_called_once_with("rev-1")


class TestSupabaseAnnualReviewRepositoryEmployeeAndCompany:
    """get_employee_company_id, get_employee_by_id, get_company_by_id."""

    def test_get_employee_company_id(self, repo: SupabaseAnnualReviewRepository):
        """get_employee_company_id délègue et retourne company_id ou None."""
        with patch(
            "app.modules.annual_reviews.infrastructure.repository.infra_queries.query_employee_company_id",
            return_value="co-1",
        ) as mock_query:
            result = repo.get_employee_company_id("emp-1")
            mock_query.assert_called_once_with("emp-1")
        assert result == "co-1"

        with patch(
            "app.modules.annual_reviews.infrastructure.repository.infra_queries.query_employee_company_id",
            return_value=None,
        ):
            result = repo.get_employee_company_id("emp-unknown")
        assert result is None

    def test_get_employee_by_id(self, repo: SupabaseAnnualReviewRepository):
        """get_employee_by_id retourne les champs employé pour le PDF."""
        emp = {"id": "emp-1", "first_name": "Jean", "last_name": "Dupont", "job_title": "Dev"}
        with patch(
            "app.modules.annual_reviews.infrastructure.repository.infra_queries.query_employee_by_id",
            return_value=emp,
        ) as mock_query:
            result = repo.get_employee_by_id("emp-1")
            mock_query.assert_called_once_with("emp-1")
        assert result == emp

    def test_get_company_by_id(self, repo: SupabaseAnnualReviewRepository):
        """get_company_by_id retourne les données entreprise."""
        company = {"id": "co-1", "name": "Test Co"}
        with patch(
            "app.modules.annual_reviews.infrastructure.repository.infra_queries.query_company_by_id",
            return_value=company,
        ) as mock_query:
            result = repo.get_company_by_id("co-1")
            mock_query.assert_called_once_with("co-1")
        assert result == company

        with patch(
            "app.modules.annual_reviews.infrastructure.repository.infra_queries.query_company_by_id",
            return_value=None,
        ):
            result = repo.get_company_by_id("co-unknown")
        assert result is None
