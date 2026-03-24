"""
Tests unitaires du MutuelleTypesService (application/service.py).

Service testé avec repository mocké (injection au constructeur).
"""
from datetime import datetime
from uuid import UUID, uuid4
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.modules.mutuelle_types.application.service import MutuelleTypesService
from app.modules.mutuelle_types.domain.entities import MutuelleType
from app.modules.mutuelle_types.schemas import MutuelleTypeCreate, MutuelleTypeUpdate


COMPANY_ID = "550e8400-e29b-41d4-a716-446655440000"
USER_ID = "660e8400-e29b-41d4-a716-446655440001"
MUTUELLE_ID = "770e8400-e29b-41d4-a716-446655440002"


def _make_mutuelle_entity(**kwargs):
    defaults = {
        "id": uuid4(),
        "company_id": UUID(COMPANY_ID),
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


class TestMutuelleTypesServiceListByCompany:
    """Service list_by_company."""

    def test_list_by_company_returns_formatted_list_with_employee_ids(self):
        entity = _make_mutuelle_entity(libelle="Formule A")
        repo = MagicMock()
        repo.list_by_company.return_value = [entity]
        repo.list_employee_ids.return_value = ["emp-1", "emp-2"]
        svc = MutuelleTypesService(repo)

        result = svc.list_by_company(COMPANY_ID)

        repo.list_by_company.assert_called_once_with(COMPANY_ID)
        repo.list_employee_ids.assert_called_once_with(str(entity.id))
        assert len(result) == 1
        assert result[0]["libelle"] == "Formule A"
        assert result[0]["employee_ids"] == ["emp-1", "emp-2"]
        assert result[0]["montant_salarial"] == 50.0

    def test_list_by_company_empty_returns_empty_list(self):
        repo = MagicMock()
        repo.list_by_company.return_value = []
        svc = MutuelleTypesService(repo)

        result = svc.list_by_company(COMPANY_ID)

        repo.list_by_company.assert_called_once_with(COMPANY_ID)
        assert result == []


class TestMutuelleTypesServiceCreate:
    """Service create."""

    def test_create_success_returns_dict_with_employee_ids(self):
        payload = MutuelleTypeCreate(
            libelle="Nouvelle formule",
            montant_salarial=60.0,
            montant_patronal=40.0,
            part_patronale_soumise_a_csg=True,
            is_active=True,
            employee_ids=[],
        )
        created = _make_mutuelle_entity(libelle="Nouvelle formule", montant_salarial=60.0)
        repo = MagicMock()
        repo.find_by_company_and_libelle.return_value = None
        repo.create.return_value = created
        repo.validate_employee_ids_belong_to_company.return_value = []
        repo.set_employee_associations.return_value = None
        svc = MutuelleTypesService(repo)

        result = svc.create(COMPANY_ID, USER_ID, payload)

        repo.find_by_company_and_libelle.assert_called_once_with(COMPANY_ID, "Nouvelle formule")
        repo.create.assert_called_once()
        assert result["libelle"] == "Nouvelle formule"
        assert result["montant_salarial"] == 60.0
        assert "employee_ids" in result

    def test_create_duplicate_libelle_raises_400(self):
        payload = MutuelleTypeCreate(
            libelle="Formule existante",
            montant_salarial=50.0,
            montant_patronal=30.0,
            part_patronale_soumise_a_csg=True,
            is_active=True,
            employee_ids=[],
        )
        existing = _make_mutuelle_entity(libelle="Formule existante", is_active=True)
        repo = MagicMock()
        repo.find_by_company_and_libelle.return_value = existing
        svc = MutuelleTypesService(repo)

        with pytest.raises(HTTPException) as exc_info:
            svc.create(COMPANY_ID, USER_ID, payload)

        assert exc_info.value.status_code == 400
        assert "existe déjà" in str(exc_info.value.detail)
        repo.create.assert_not_called()

    def test_create_invalid_employee_ids_raises_400(self):
        payload = MutuelleTypeCreate(
            libelle="Formule",
            montant_salarial=50.0,
            montant_patronal=30.0,
            part_patronale_soumise_a_csg=True,
            is_active=True,
            employee_ids=["emp-1", "emp-invalid"],
        )
        created = _make_mutuelle_entity()
        repo = MagicMock()
        repo.find_by_company_and_libelle.return_value = None
        repo.create.return_value = created
        repo.validate_employee_ids_belong_to_company.return_value = ["emp-1"]
        svc = MutuelleTypesService(repo)

        with pytest.raises(HTTPException) as exc_info:
            svc.create(COMPANY_ID, USER_ID, payload)

        assert exc_info.value.status_code == 400
        assert "n'appartiennent pas" in str(exc_info.value.detail)


class TestMutuelleTypesServiceUpdate:
    """Service update."""

    def test_update_success_returns_dict(self):
        payload = MutuelleTypeUpdate(
            libelle="Formule mise à jour",
            montant_salarial=70.0,
            montant_patronal=45.0,
        )
        existing = _make_mutuelle_entity(company_id=UUID(COMPANY_ID), libelle="Ancien")
        updated = _make_mutuelle_entity(
            libelle="Formule mise à jour",
            montant_salarial=70.0,
            montant_patronal=45.0,
        )
        repo = MagicMock()
        repo.get_by_id.return_value = existing
        repo.find_by_company_and_libelle.return_value = None
        repo.update.return_value = updated
        repo.list_employee_ids.return_value = []
        svc = MutuelleTypesService(repo)

        result = svc.update(MUTUELLE_ID, COMPANY_ID, USER_ID, payload)

        repo.get_by_id.assert_called_once_with(MUTUELLE_ID, COMPANY_ID)
        repo.update.assert_called_once()
        assert result["libelle"] == "Formule mise à jour"
        assert result["montant_salarial"] == 70.0

    def test_update_not_found_raises_404(self):
        payload = MutuelleTypeUpdate(libelle="X")
        repo = MagicMock()
        repo.get_by_id.return_value = None
        svc = MutuelleTypesService(repo)

        with pytest.raises(HTTPException) as exc_info:
            svc.update(MUTUELLE_ID, COMPANY_ID, USER_ID, payload)

        assert exc_info.value.status_code == 404
        assert "non trouvée" in str(exc_info.value.detail)
        repo.update.assert_not_called()

    def test_update_wrong_company_raises_403(self):
        payload = MutuelleTypeUpdate(libelle="X")
        existing = _make_mutuelle_entity(company_id=uuid4())
        repo = MagicMock()
        repo.get_by_id.return_value = existing
        svc = MutuelleTypesService(repo)

        with pytest.raises(HTTPException) as exc_info:
            svc.update(MUTUELLE_ID, COMPANY_ID, USER_ID, payload)

        assert exc_info.value.status_code == 403
        assert "n'appartient pas" in str(exc_info.value.detail)


class TestMutuelleTypesServiceDelete:
    """Service delete."""

    def test_delete_success_returns_status(self):
        existing = _make_mutuelle_entity(company_id=UUID(COMPANY_ID), libelle="À supprimer")
        repo = MagicMock()
        repo.get_by_id.return_value = existing
        repo.list_employee_ids.return_value = ["emp-1"]
        repo.remove_employee_associations_and_sync_specificites.return_value = None
        repo.delete.return_value = True
        svc = MutuelleTypesService(repo)

        result = svc.delete(MUTUELLE_ID, COMPANY_ID)

        repo.get_by_id.assert_called_once_with(MUTUELLE_ID, COMPANY_ID)
        repo.list_employee_ids.assert_called_once_with(MUTUELLE_ID)
        repo.remove_employee_associations_and_sync_specificites.assert_called_once_with(
            MUTUELLE_ID, ["emp-1"]
        )
        repo.delete.assert_called_once_with(MUTUELLE_ID)
        assert result["status"] == "success"
        assert "supprimée" in result["message"].lower()

    def test_delete_not_found_raises_404(self):
        repo = MagicMock()
        repo.get_by_id.return_value = None
        svc = MutuelleTypesService(repo)

        with pytest.raises(HTTPException) as exc_info:
            svc.delete(MUTUELLE_ID, COMPANY_ID)

        assert exc_info.value.status_code == 404
        repo.delete.assert_not_called()

    def test_delete_wrong_company_raises_403(self):
        existing = _make_mutuelle_entity(company_id=uuid4())
        repo = MagicMock()
        repo.get_by_id.return_value = existing
        svc = MutuelleTypesService(repo)

        with pytest.raises(HTTPException) as exc_info:
            svc.delete(MUTUELLE_ID, COMPANY_ID)

        assert exc_info.value.status_code == 403
        repo.delete.assert_not_called()
