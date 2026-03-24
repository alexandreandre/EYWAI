"""
Tests unitaires des requêtes bonus_types (application/queries.py).

Chaque query est testée avec un service mocké injecté.
"""
from uuid import uuid4

from app.modules.bonus_types.application.dto import BonusCalculationResult
from app.modules.bonus_types.application.queries import (
    list_bonus_types_by_company,
    get_bonus_type_by_id,
    calculate_bonus_amount,
)
from app.modules.bonus_types.domain.entities import BonusType
from app.modules.bonus_types.domain.enums import BonusTypeKind


def _make_mock_service():
    from unittest.mock import MagicMock
    return MagicMock()


class TestListBonusTypesByCompany:
    """Query list_bonus_types_by_company."""

    def test_list_calls_service_list_by_company(self):
        company_id = "co-123"
        entity = BonusType(
            id=uuid4(),
            company_id=uuid4(),
            libelle="Prime A",
            type=BonusTypeKind.MONTANT_FIXE,
            montant=100.0,
            seuil_heures=None,
            soumise_a_cotisations=True,
            soumise_a_impot=True,
            prompt_ia=None,
        )
        mock_svc = _make_mock_service()
        mock_svc.list_by_company.return_value = [entity]

        result = list_bonus_types_by_company(company_id, service=mock_svc)

        mock_svc.list_by_company.assert_called_once_with(company_id)
        assert len(result) == 1
        assert result[0].libelle == "Prime A"

    def test_list_returns_empty_list(self):
        mock_svc = _make_mock_service()
        mock_svc.list_by_company.return_value = []

        result = list_bonus_types_by_company("co-empty", service=mock_svc)

        assert result == []


class TestGetBonusTypeById:
    """Query get_bonus_type_by_id."""

    def test_get_by_id_calls_service_get_by_id(self):
        bonus_id = "bt-456"
        company_id = "co-789"
        entity = BonusType(
            id=uuid4(),
            company_id=uuid4(),
            libelle="Prime B",
            type=BonusTypeKind.SELON_HEURES,
            montant=80.0,
            seuil_heures=151.67,
            soumise_a_cotisations=True,
            soumise_a_impot=True,
            prompt_ia=None,
        )
        mock_svc = _make_mock_service()
        mock_svc.get_by_id.return_value = entity

        result = get_bonus_type_by_id(bonus_id, company_id=company_id, service=mock_svc)

        mock_svc.get_by_id.assert_called_once_with(bonus_id, company_id)
        assert result is not None
        assert result.libelle == "Prime B"
        assert result.seuil_heures == 151.67

    def test_get_by_id_without_company_id(self):
        mock_svc = _make_mock_service()
        mock_svc.get_by_id.return_value = None

        result = get_bonus_type_by_id("bt-1", company_id=None, service=mock_svc)

        mock_svc.get_by_id.assert_called_once_with("bt-1", None)
        assert result is None

    def test_get_by_id_returns_none_when_not_found(self):
        mock_svc = _make_mock_service()
        mock_svc.get_by_id.return_value = None

        result = get_bonus_type_by_id("unknown", "co-1", service=mock_svc)

        assert result is None


class TestCalculateBonusAmount:
    """Query calculate_bonus_amount."""

    def test_calculate_calls_service_calculate_amount(self):
        mock_svc = _make_mock_service()
        mock_svc.calculate_amount.return_value = BonusCalculationResult(
            amount=100.0,
            calculated=True,
            total_hours=None,
            seuil=None,
            condition_met=None,
        )

        result = calculate_bonus_amount(
            "bt-1",
            "co-1",
            "emp-1",
            year=2025,
            month=3,
            service=mock_svc,
        )

        mock_svc.calculate_amount.assert_called_once_with(
            "bt-1", "co-1", "emp-1", 2025, 3
        )
        assert result.amount == 100.0
        assert result.calculated is True

    def test_calculate_returns_selon_heures_result(self):
        mock_svc = _make_mock_service()
        mock_svc.calculate_amount.return_value = BonusCalculationResult(
            amount=80.0,
            calculated=True,
            total_hours=160.0,
            seuil=151.67,
            condition_met=True,
        )

        result = calculate_bonus_amount(
            "bt-heures",
            "co-1",
            "emp-1",
            year=2025,
            month=2,
            service=mock_svc,
        )

        assert result.total_hours == 160.0
        assert result.seuil == 151.67
        assert result.condition_met is True
