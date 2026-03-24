"""
Tests unitaires des commandes bonus_types (application/commands.py).

Chaque commande est testée avec un service mocké injecté.
"""
from datetime import datetime
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.modules.bonus_types.application.commands import (
    create_bonus_type,
    update_bonus_type,
    delete_bonus_type,
)
from app.modules.bonus_types.application.dto import (
    BonusTypeCreateInput,
    BonusTypeUpdateInput,
)
from app.modules.bonus_types.domain.entities import BonusType
from app.modules.bonus_types.domain.enums import BonusTypeKind


def _make_mock_service():
    """Crée un mock du BonusTypesService avec comportement configurable."""
    from unittest.mock import MagicMock
    return MagicMock()


class TestCreateBonusType:
    """Commande create_bonus_type."""

    def test_create_bonus_type_calls_service_create(self):
        company_id = uuid4()
        user_id = uuid4()
        input_data = BonusTypeCreateInput(
            libelle="Prime exceptionnelle",
            type="montant_fixe",
            montant=500.0,
            seuil_heures=None,
            soumise_a_cotisations=True,
            soumise_a_impot=True,
            prompt_ia=None,
            company_id=company_id,
            created_by=user_id,
        )
        created_entity = BonusType(
            id=uuid4(),
            company_id=company_id,
            libelle="Prime exceptionnelle",
            type=BonusTypeKind.MONTANT_FIXE,
            montant=500.0,
            seuil_heures=None,
            soumise_a_cotisations=True,
            soumise_a_impot=True,
            prompt_ia=None,
            created_at=datetime.now(),
            updated_at=None,
            created_by=user_id,
        )
        mock_svc = _make_mock_service()
        mock_svc.create.return_value = created_entity

        result = create_bonus_type(input_data, has_rh_access=True, service=mock_svc)

        mock_svc.create.assert_called_once_with(input_data, True)
        assert result.id == created_entity.id
        assert result.libelle == "Prime exceptionnelle"
        assert result.montant == 500.0

    def test_create_bonus_type_without_rh_access_raises(self):
        company_id = uuid4()
        user_id = uuid4()
        input_data = BonusTypeCreateInput(
            libelle="Prime",
            type="montant_fixe",
            montant=100.0,
            seuil_heures=None,
            soumise_a_cotisations=True,
            soumise_a_impot=True,
            prompt_ia=None,
            company_id=company_id,
            created_by=user_id,
        )
        mock_svc = _make_mock_service()
        mock_svc.create.side_effect = HTTPException(status_code=403, detail="Seuls les Admin/RH...")

        with pytest.raises(HTTPException) as exc_info:
            create_bonus_type(input_data, has_rh_access=False, service=mock_svc)

        assert exc_info.value.status_code == 403


class TestUpdateBonusType:
    """Commande update_bonus_type."""

    def test_update_bonus_type_calls_service_update(self):
        bonus_id = "bt-123"
        company_id = "co-456"
        input_data = BonusTypeUpdateInput(
            libelle="Prime mise à jour",
            montant=150.0,
        )
        updated_entity = BonusType(
            id=uuid4(),
            company_id=uuid4(),
            libelle="Prime mise à jour",
            type=BonusTypeKind.MONTANT_FIXE,
            montant=150.0,
            seuil_heures=None,
            soumise_a_cotisations=True,
            soumise_a_impot=True,
            prompt_ia=None,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            created_by=uuid4(),
        )
        mock_svc = _make_mock_service()
        mock_svc.update.return_value = updated_entity

        result = update_bonus_type(
            bonus_id, company_id, has_rh_access=True, input_data=input_data, service=mock_svc
        )

        mock_svc.update.assert_called_once_with(
            bonus_id, company_id, True, input_data
        )
        assert result is not None
        assert result.libelle == "Prime mise à jour"
        assert result.montant == 150.0

    def test_update_bonus_type_returns_none_when_not_found(self):
        mock_svc = _make_mock_service()
        mock_svc.update.return_value = None

        result = update_bonus_type(
            "unknown-id",
            "co-456",
            has_rh_access=True,
            input_data=BonusTypeUpdateInput(libelle="X"),
            service=mock_svc,
        )

        assert result is None


class TestDeleteBonusType:
    """Commande delete_bonus_type."""

    def test_delete_bonus_type_calls_service_delete(self):
        bonus_id = "bt-789"
        company_id = "co-abc"
        mock_svc = _make_mock_service()
        mock_svc.delete.return_value = True

        result = delete_bonus_type(
            bonus_id,
            company_id,
            is_super_admin=False,
            has_rh_access=True,
            service=mock_svc,
        )

        mock_svc.delete.assert_called_once_with(
            bonus_id, company_id, False, True
        )
        assert result is True

    def test_delete_bonus_type_super_admin_allowed(self):
        mock_svc = _make_mock_service()
        mock_svc.delete.return_value = True

        result = delete_bonus_type(
            "bt-1",
            "co-1",
            is_super_admin=True,
            has_rh_access=False,
            service=mock_svc,
        )

        mock_svc.delete.assert_called_once_with("bt-1", "co-1", True, False)
        assert result is True
