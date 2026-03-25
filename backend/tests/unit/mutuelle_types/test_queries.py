"""
Tests unitaires des requêtes mutuelle_types (application/queries.py).

list_mutuelle_types est testée en mockant SupabaseMutuelleTypeRepository (patch).
"""

from datetime import datetime
from uuid import uuid4
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.modules.mutuelle_types.application.queries import list_mutuelle_types
from app.modules.mutuelle_types.domain.entities import MutuelleType


COMPANY_ID = "550e8400-e29b-41d4-a716-446655440000"


def _make_mutuelle_entity(**kwargs):
    defaults = {
        "id": uuid4(),
        "company_id": uuid4(),
        "libelle": "Formule Test",
        "montant_salarial": 50.0,
        "montant_patronal": 30.0,
        "part_patronale_soumise_a_csg": True,
        "is_active": True,
        "created_at": datetime.now(),
        "updated_at": None,
        "created_by": None,
    }
    defaults.update(kwargs)
    return MutuelleType(**defaults)


class TestListMutuelleTypes:
    """Query list_mutuelle_types."""

    def test_list_mutuelle_types_calls_repo_and_returns_list_of_dicts(self):
        entity_a = _make_mutuelle_entity(libelle="Formule A")
        entity_b = _make_mutuelle_entity(libelle="Formule B")
        mock_repo = MagicMock()
        mock_repo.list_by_company.return_value = [entity_a, entity_b]
        mock_repo.list_employee_ids.side_effect = [["emp-1"], ["emp-2"]]

        with patch(
            "app.modules.mutuelle_types.application.queries.SupabaseMutuelleTypeRepository",
            return_value=mock_repo,
        ):
            result = list_mutuelle_types(COMPANY_ID)

        mock_repo.list_by_company.assert_called_once_with(COMPANY_ID)
        assert len(result) == 2
        assert result[0]["libelle"] == "Formule A"
        assert result[1]["libelle"] == "Formule B"
        assert "employee_ids" in result[0]
        assert result[0]["employee_ids"] == ["emp-1"]
        assert result[1]["employee_ids"] == ["emp-2"]
        assert mock_repo.list_employee_ids.call_count == 2

    def test_list_mutuelle_types_empty_returns_empty_list(self):
        mock_repo = MagicMock()
        mock_repo.list_by_company.return_value = []

        with patch(
            "app.modules.mutuelle_types.application.queries.SupabaseMutuelleTypeRepository",
            return_value=mock_repo,
        ):
            result = list_mutuelle_types(COMPANY_ID)

        mock_repo.list_by_company.assert_called_once_with(COMPANY_ID)
        assert result == []

    def test_list_mutuelle_types_single_item_with_no_employees(self):
        entity = _make_mutuelle_entity(libelle="Solo")
        mock_repo = MagicMock()
        mock_repo.list_by_company.return_value = [entity]
        mock_repo.list_employee_ids.return_value = []

        with patch(
            "app.modules.mutuelle_types.application.queries.SupabaseMutuelleTypeRepository",
            return_value=mock_repo,
        ):
            result = list_mutuelle_types(COMPANY_ID)

        assert len(result) == 1
        assert result[0]["libelle"] == "Solo"
        assert result[0]["employee_ids"] == []
        assert result[0]["montant_salarial"] == 50.0
        assert result[0]["montant_patronal"] == 30.0
        assert "id" in result[0]
        assert "company_id" in result[0]

    def test_list_mutuelle_types_raises_500_on_generic_exception(self):
        mock_repo = MagicMock()
        mock_repo.list_by_company.side_effect = RuntimeError("DB error")

        with patch(
            "app.modules.mutuelle_types.application.queries.SupabaseMutuelleTypeRepository",
            return_value=mock_repo,
        ):
            with pytest.raises(HTTPException) as exc_info:
                list_mutuelle_types(COMPANY_ID)

        assert exc_info.value.status_code == 500
        assert "mutuelles" in str(exc_info.value.detail).lower() or "Erreur" in str(
            exc_info.value.detail
        )
