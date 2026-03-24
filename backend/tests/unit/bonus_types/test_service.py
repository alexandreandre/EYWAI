"""
Tests unitaires du BonusTypesService (application/service.py).

Service testé avec repository et (optionnel) IEmployeeHoursProvider mockés.
"""
from datetime import datetime
from uuid import uuid4

import pytest
from fastapi import HTTPException
from unittest.mock import MagicMock

from app.modules.bonus_types.application.dto import (
    BonusTypeCreateInput,
    BonusTypeUpdateInput,
)
from app.modules.bonus_types.application.service import BonusTypesService
from app.modules.bonus_types.domain.entities import BonusType
from app.modules.bonus_types.domain.enums import BonusTypeKind


def _make_bonus_entity(**kwargs):
    defaults = {
        "id": uuid4(),
        "company_id": uuid4(),
        "libelle": "Prime test",
        "type": BonusTypeKind.MONTANT_FIXE,
        "montant": 100.0,
        "seuil_heures": None,
        "soumise_a_cotisations": True,
        "soumise_a_impot": True,
        "prompt_ia": None,
        "created_at": None,
        "updated_at": None,
        "created_by": None,
    }
    defaults.update(kwargs)
    return BonusType(**defaults)


class TestBonusTypesServiceListByCompany:
    """Service list_by_company."""

    def test_list_by_company_returns_repo_result(self):
        repo = MagicMock()
        entity = _make_bonus_entity(libelle="Prime A")
        repo.list_by_company.return_value = [entity]
        svc = BonusTypesService(repo)

        result = svc.list_by_company("co-1")

        repo.list_by_company.assert_called_once_with("co-1")
        assert len(result) == 1
        assert result[0].libelle == "Prime A"

    def test_list_by_company_empty_company_raises_400(self):
        repo = MagicMock()
        svc = BonusTypesService(repo)

        with pytest.raises(HTTPException) as exc_info:
            svc.list_by_company("")

        assert exc_info.value.status_code == 400
        assert "Aucune entreprise active" in exc_info.value.detail
        repo.list_by_company.assert_not_called()


class TestBonusTypesServiceGetById:
    """Service get_by_id."""

    def test_get_by_id_returns_repo_result(self):
        repo = MagicMock()
        entity = _make_bonus_entity(libelle="Prime B")
        repo.get_by_id.return_value = entity
        svc = BonusTypesService(repo)

        result = svc.get_by_id("bt-1", "co-1")

        repo.get_by_id.assert_called_once_with("bt-1", "co-1")
        assert result is not None
        assert result.libelle == "Prime B"

    def test_get_by_id_returns_none(self):
        repo = MagicMock()
        repo.get_by_id.return_value = None
        svc = BonusTypesService(repo)

        result = svc.get_by_id("unknown", "co-1")

        assert result is None


class TestBonusTypesServiceCreate:
    """Service create."""

    def test_create_success_returns_entity(self):
        repo = MagicMock()
        created = _make_bonus_entity(id=uuid4(), libelle="Nouvelle prime")
        repo.create.return_value = created
        svc = BonusTypesService(repo)
        input_data = BonusTypeCreateInput(
            libelle="Nouvelle prime",
            type="montant_fixe",
            montant=200.0,
            seuil_heures=None,
            soumise_a_cotisations=True,
            soumise_a_impot=True,
            prompt_ia=None,
            company_id=uuid4(),
            created_by=uuid4(),
        )

        result = svc.create(input_data, has_rh_access=True)

        repo.create.assert_called_once()
        call_entity = repo.create.call_args[0][0]
        assert call_entity.libelle == "Nouvelle prime"
        assert call_entity.montant == 200.0
        assert result.id == created.id

    def test_create_without_company_raises_400(self):
        repo = MagicMock()
        svc = BonusTypesService(repo)
        # Simuler un payload sans company_id (contexte utilisateur sans entreprise active)
        input_data = MagicMock(spec=BonusTypeCreateInput)
        input_data.company_id = None
        input_data.libelle = "X"
        input_data.type = "montant_fixe"
        input_data.montant = 0.0
        input_data.seuil_heures = None
        input_data.soumise_a_cotisations = True
        input_data.soumise_a_impot = True
        input_data.prompt_ia = None
        input_data.created_by = uuid4()

        with pytest.raises(HTTPException) as exc_info:
            svc.create(input_data, has_rh_access=True)

        assert exc_info.value.status_code == 400
        assert "Aucune entreprise active" in exc_info.value.detail
        repo.create.assert_not_called()

    def test_create_without_rh_access_raises_403(self):
        repo = MagicMock()
        svc = BonusTypesService(repo)
        input_data = BonusTypeCreateInput(
            libelle="X",
            type="montant_fixe",
            montant=100.0,
            seuil_heures=None,
            soumise_a_cotisations=True,
            soumise_a_impot=True,
            prompt_ia=None,
            company_id=uuid4(),
            created_by=uuid4(),
        )

        with pytest.raises(HTTPException) as exc_info:
            svc.create(input_data, has_rh_access=False)

        assert exc_info.value.status_code == 403
        assert "Admin/RH" in exc_info.value.detail
        repo.create.assert_not_called()


class TestBonusTypesServiceUpdate:
    """Service update."""

    def test_update_success_returns_entity(self):
        repo = MagicMock()
        company_uuid = uuid4()
        existing = _make_bonus_entity(libelle="Ancien", company_id=company_uuid)
        updated = _make_bonus_entity(libelle="Mis à jour", montant=150.0, company_id=company_uuid)
        repo.get_by_id.return_value = existing
        repo.update.return_value = updated
        svc = BonusTypesService(repo)
        input_data = BonusTypeUpdateInput(libelle="Mis à jour", montant=150.0)

        result = svc.update("bt-1", str(company_uuid), True, input_data)

        repo.update.assert_called_once()
        assert result is not None
        assert result.libelle == "Mis à jour"

    def test_update_not_found_raises_404(self):
        repo = MagicMock()
        repo.get_by_id.return_value = None
        svc = BonusTypesService(repo)

        with pytest.raises(HTTPException) as exc_info:
            svc.update("bt-1", "co-1", True, BonusTypeUpdateInput(libelle="X"))

        assert exc_info.value.status_code == 404
        repo.update.assert_not_called()

    def test_update_without_rh_access_raises_403(self):
        repo = MagicMock()
        svc = BonusTypesService(repo)

        with pytest.raises(HTTPException) as exc_info:
            svc.update(
                "bt-1",
                "co-1",
                has_rh_access=False,
                input_data=BonusTypeUpdateInput(libelle="X"),
            )

        assert exc_info.value.status_code == 403
        repo.get_by_id.assert_not_called()


class TestBonusTypesServiceDelete:
    """Service delete."""

    def test_delete_success_returns_true(self):
        repo = MagicMock()
        company_uuid = uuid4()
        existing = _make_bonus_entity(company_id=company_uuid)
        repo.get_by_id.return_value = existing
        svc = BonusTypesService(repo)

        result = svc.delete("bt-1", str(company_uuid), False, True)

        repo.delete.assert_called_once_with("bt-1")
        assert result is True

    def test_delete_not_found_raises_404(self):
        repo = MagicMock()
        repo.get_by_id.return_value = None
        svc = BonusTypesService(repo)

        with pytest.raises(HTTPException) as exc_info:
            svc.delete("bt-1", "co-1", False, True)

        assert exc_info.value.status_code == 404
        repo.delete.assert_not_called()

    def test_delete_without_rh_nor_super_admin_raises_403(self):
        repo = MagicMock()
        svc = BonusTypesService(repo)

        with pytest.raises(HTTPException) as exc_info:
            svc.delete("bt-1", "co-1", is_super_admin=False, has_rh_access=False)

        assert exc_info.value.status_code == 403
        repo.get_by_id.assert_not_called()


class TestBonusTypesServiceCalculateAmount:
    """Service calculate_amount."""

    def test_calculate_amount_montant_fixe_uses_rules(self):
        repo = MagicMock()
        bonus = _make_bonus_entity(type=BonusTypeKind.MONTANT_FIXE, montant=300.0)
        repo.get_by_id.return_value = bonus
        hours_provider = MagicMock()
        hours_provider.get_total_actual_hours.return_value = 0.0
        svc = BonusTypesService(repo, hours_provider=hours_provider)

        result = svc.calculate_amount("bt-1", "co-1", "emp-1", 2025, 3)

        assert result.amount == 300.0
        assert result.calculated is True
        assert result.total_hours is None

    def test_calculate_amount_selon_heures_uses_provider(self):
        repo = MagicMock()
        bonus = _make_bonus_entity(
            type=BonusTypeKind.SELON_HEURES,
            montant=80.0,
            seuil_heures=151.67,
        )
        repo.get_by_id.return_value = bonus
        hours_provider = MagicMock()
        hours_provider.get_total_actual_hours.return_value = 160.0
        svc = BonusTypesService(repo, hours_provider=hours_provider)

        result = svc.calculate_amount("bt-1", "co-1", "emp-1", 2025, 3)

        hours_provider.get_total_actual_hours.assert_called_once_with(
            "emp-1", 2025, 3
        )
        assert result.amount == 80.0
        assert result.total_hours == 160.0
        assert result.seuil == 151.67
        assert result.condition_met is True

    def test_calculate_amount_bonus_not_found_raises_404(self):
        repo = MagicMock()
        repo.get_by_id.return_value = None
        svc = BonusTypesService(repo)

        with pytest.raises(HTTPException) as exc_info:
            svc.calculate_amount("bt-1", "co-1", "emp-1", 2025, 3)

        assert exc_info.value.status_code == 404
        assert "Prime non trouvée" in exc_info.value.detail
