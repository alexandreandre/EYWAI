"""
Tests d'intégration du repository residence_permits (ResidencePermitListRepository).

Sans DB de test : mock de fetch_employees_for_residence_permits_list (infrastructure.queries)
pour valider que le repository délègue correctement et retourne la liste.
Avec DB de test : prévoir la fixture db_session (conftest) et des données dans employees
(is_subject_to_residence_permit=True, employment_status in ('actif','en_sortie'))
pour des tests contre une vraie base.
"""
from unittest.mock import MagicMock, patch

import pytest

from app.modules.residence_permits.infrastructure.repository import (
    ResidencePermitListRepository,
)


pytestmark = pytest.mark.integration

COMPANY_ID = "550e8400-e29b-41d4-a716-446655440000"


def _row(employee_id: str = "emp-1", **kwargs):
    base = {
        "id": employee_id,
        "first_name": "Jean",
        "last_name": "Dupont",
        "is_subject_to_residence_permit": True,
        "residence_permit_expiry_date": "2026-06-15",
        "residence_permit_type": None,
        "residence_permit_number": None,
        "employment_status": "actif",
    }
    base.update(kwargs)
    return base


class TestResidencePermitListRepositoryGetEmployeesSubject:
    """get_employees_subject_for_company(company_id)."""

    @patch(
        "app.modules.residence_permits.infrastructure.repository."
        "fetch_employees_for_residence_permits_list"
    )
    def test_delegates_to_fetch_and_returns_list(
        self, mock_fetch: MagicMock
    ):
        """Le repository appelle fetch_employees_for_residence_permits_list et retourne la liste."""
        mock_fetch.return_value = [
            _row("emp-1"),
            _row("emp-2", first_name="Marie", last_name="Martin"),
        ]
        repo = ResidencePermitListRepository()
        result = repo.get_employees_subject_for_company(COMPANY_ID)

        mock_fetch.assert_called_once_with(COMPANY_ID)
        assert len(result) == 2
        assert result[0]["id"] == "emp-1"
        assert result[0]["last_name"] == "Dupont"
        assert result[1]["id"] == "emp-2"
        assert result[1]["first_name"] == "Marie"

    @patch(
        "app.modules.residence_permits.infrastructure.repository."
        "fetch_employees_for_residence_permits_list"
    )
    def test_empty_list_when_no_employees(self, mock_fetch: MagicMock):
        """Aucun employé soumis → liste vide."""
        mock_fetch.return_value = []
        repo = ResidencePermitListRepository()
        result = repo.get_employees_subject_for_company(COMPANY_ID)

        mock_fetch.assert_called_once_with(COMPANY_ID)
        assert result == []

    @patch(
        "app.modules.residence_permits.infrastructure.repository."
        "fetch_employees_for_residence_permits_list"
    )
    def test_different_company_id_passed_to_fetch(self, mock_fetch: MagicMock):
        """Le company_id passé au repo est transmis à fetch."""
        mock_fetch.return_value = []
        repo = ResidencePermitListRepository()
        other_company = "660e8400-e29b-41d4-a716-446655440001"
        repo.get_employees_subject_for_company(other_company)

        mock_fetch.assert_called_once_with(other_company)
