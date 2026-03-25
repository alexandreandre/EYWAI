"""
Tests unitaires des commandes mutuelle_types (application/commands.py).

Chaque commande est testée en mockant SupabaseMutuelleTypeRepository (injection via patch).
"""

from datetime import datetime
from uuid import uuid4
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.modules.mutuelle_types.application.commands import (
    create_mutuelle_type,
    update_mutuelle_type,
    delete_mutuelle_type,
)
from uuid import UUID

from app.modules.mutuelle_types.domain.entities import MutuelleType
from app.modules.mutuelle_types.schemas import MutuelleTypeCreate, MutuelleTypeUpdate


COMPANY_ID = "550e8400-e29b-41d4-a716-446655440000"
USER_ID = "660e8400-e29b-41d4-a716-446655440001"
MUTUELLE_ID = "770e8400-e29b-41d4-a716-446655440002"


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


class TestCreateMutuelleType:
    """Commande create_mutuelle_type."""

    def test_create_mutuelle_type_success_returns_dict(self):
        payload = MutuelleTypeCreate(
            libelle="Nouvelle formule",
            montant_salarial=60.0,
            montant_patronal=40.0,
            part_patronale_soumise_a_csg=True,
            is_active=True,
            employee_ids=[],
        )
        created_entity = _make_mutuelle_entity(
            libelle="Nouvelle formule",
            montant_salarial=60.0,
            montant_patronal=40.0,
        )
        mock_repo = MagicMock()
        mock_repo.find_by_company_and_libelle.return_value = None
        mock_repo.create.return_value = created_entity
        mock_repo.validate_employee_ids_belong_to_company.return_value = []
        mock_repo.set_employee_associations.return_value = None

        with patch(
            "app.modules.mutuelle_types.application.commands.SupabaseMutuelleTypeRepository",
            return_value=mock_repo,
        ):
            result = create_mutuelle_type(COMPANY_ID, USER_ID, payload)

        mock_repo.find_by_company_and_libelle.assert_called_once_with(
            COMPANY_ID, "Nouvelle formule"
        )
        mock_repo.create.assert_called_once()
        assert result["libelle"] == "Nouvelle formule"
        assert result["montant_salarial"] == 60.0
        assert result["montant_patronal"] == 40.0
        assert "employee_ids" in result

    def test_create_mutuelle_type_with_employee_ids_validates_and_sets_associations(
        self,
    ):
        payload = MutuelleTypeCreate(
            libelle="Formule avec employés",
            montant_salarial=50.0,
            montant_patronal=30.0,
            part_patronale_soumise_a_csg=True,
            is_active=True,
            employee_ids=["emp-1", "emp-2"],
        )
        created_entity = _make_mutuelle_entity(libelle="Formule avec employés")
        mock_repo = MagicMock()
        mock_repo.find_by_company_and_libelle.return_value = None
        mock_repo.create.return_value = created_entity
        mock_repo.validate_employee_ids_belong_to_company.return_value = [
            "emp-1",
            "emp-2",
        ]
        mock_repo.set_employee_associations.return_value = None

        with patch(
            "app.modules.mutuelle_types.application.commands.SupabaseMutuelleTypeRepository",
            return_value=mock_repo,
        ):
            create_mutuelle_type(COMPANY_ID, USER_ID, payload)

        mock_repo.validate_employee_ids_belong_to_company.assert_called_once_with(
            COMPANY_ID, ["emp-1", "emp-2"]
        )
        mock_repo.set_employee_associations.assert_called_once()
        call_args = mock_repo.set_employee_associations.call_args[0]
        # set_employee_associations(mutuelle_type_id, employee_ids, created_by, company_id)
        assert call_args[1] == ["emp-1", "emp-2"]
        assert call_args[2] == USER_ID
        assert call_args[3] == COMPANY_ID

    def test_create_mutuelle_type_duplicate_libelle_raises_400(self):
        payload = MutuelleTypeCreate(
            libelle="Formule existante",
            montant_salarial=50.0,
            montant_patronal=30.0,
            part_patronale_soumise_a_csg=True,
            is_active=True,
            employee_ids=[],
        )
        existing = _make_mutuelle_entity(libelle="Formule existante", is_active=True)
        mock_repo = MagicMock()
        mock_repo.find_by_company_and_libelle.return_value = existing

        with patch(
            "app.modules.mutuelle_types.application.commands.SupabaseMutuelleTypeRepository",
            return_value=mock_repo,
        ):
            with pytest.raises(HTTPException) as exc_info:
                create_mutuelle_type(COMPANY_ID, USER_ID, payload)

        assert exc_info.value.status_code == 400
        assert "Formule existante" in str(exc_info.value.detail)
        assert "existe déjà" in str(exc_info.value.detail)
        mock_repo.create.assert_not_called()

    def test_create_mutuelle_type_invalid_employee_ids_raises_400(self):
        payload = MutuelleTypeCreate(
            libelle="Formule",
            montant_salarial=50.0,
            montant_patronal=30.0,
            part_patronale_soumise_a_csg=True,
            is_active=True,
            employee_ids=["emp-1", "emp-invalid"],
        )
        created_entity = _make_mutuelle_entity()
        mock_repo = MagicMock()
        mock_repo.find_by_company_and_libelle.return_value = None
        mock_repo.create.return_value = created_entity
        # seulement emp-1 appartient à l'entreprise
        mock_repo.validate_employee_ids_belong_to_company.return_value = ["emp-1"]

        with patch(
            "app.modules.mutuelle_types.application.commands.SupabaseMutuelleTypeRepository",
            return_value=mock_repo,
        ):
            with pytest.raises(HTTPException) as exc_info:
                create_mutuelle_type(COMPANY_ID, USER_ID, payload)

        assert exc_info.value.status_code == 400
        assert "n'appartiennent pas" in str(exc_info.value.detail)


class TestUpdateMutuelleType:
    """Commande update_mutuelle_type."""

    def test_update_mutuelle_type_success_returns_dict(self):
        payload = MutuelleTypeUpdate(
            libelle="Formule mise à jour",
            montant_salarial=70.0,
            montant_patronal=45.0,
        )
        existing = _make_mutuelle_entity(
            id=uuid4(),
            company_id=UUID(COMPANY_ID),
            libelle="Formule Test",
        )
        updated_entity = _make_mutuelle_entity(
            libelle="Formule mise à jour",
            montant_salarial=70.0,
            montant_patronal=45.0,
        )
        mock_repo = MagicMock()
        mock_repo.get_by_id.return_value = existing
        mock_repo.find_by_company_and_libelle.return_value = None
        mock_repo.update.return_value = updated_entity
        mock_repo.list_employee_ids.return_value = []

        with patch(
            "app.modules.mutuelle_types.application.commands.SupabaseMutuelleTypeRepository",
            return_value=mock_repo,
        ):
            result = update_mutuelle_type(MUTUELLE_ID, COMPANY_ID, USER_ID, payload)

        mock_repo.get_by_id.assert_called_once_with(MUTUELLE_ID, COMPANY_ID)
        mock_repo.update.assert_called_once()
        assert result["libelle"] == "Formule mise à jour"
        assert result["montant_salarial"] == 70.0

    def test_update_mutuelle_type_not_found_raises_404(self):
        payload = MutuelleTypeUpdate(libelle="Nouveau libellé")
        mock_repo = MagicMock()
        mock_repo.get_by_id.return_value = None

        with patch(
            "app.modules.mutuelle_types.application.commands.SupabaseMutuelleTypeRepository",
            return_value=mock_repo,
        ):
            with pytest.raises(HTTPException) as exc_info:
                update_mutuelle_type(MUTUELLE_ID, COMPANY_ID, USER_ID, payload)

        assert exc_info.value.status_code == 404
        assert "non trouvée" in str(exc_info.value.detail)
        mock_repo.update.assert_not_called()

    def test_update_mutuelle_type_wrong_company_raises_403(self):
        payload = MutuelleTypeUpdate(libelle="X")
        existing = _make_mutuelle_entity(
            company_id=uuid4()
        )  # autre company que COMPANY_ID
        mock_repo = MagicMock()
        mock_repo.get_by_id.return_value = existing

        with patch(
            "app.modules.mutuelle_types.application.commands.SupabaseMutuelleTypeRepository",
            return_value=mock_repo,
        ):
            with pytest.raises(HTTPException) as exc_info:
                update_mutuelle_type(MUTUELLE_ID, COMPANY_ID, USER_ID, payload)

        assert exc_info.value.status_code == 403
        assert "n'appartient pas" in str(exc_info.value.detail)

    def test_update_mutuelle_type_duplicate_libelle_raises_400(self):
        payload = MutuelleTypeUpdate(libelle="Autre formule existante")
        existing = _make_mutuelle_entity(
            company_id=UUID(COMPANY_ID), libelle="Formule Test"
        )
        other = _make_mutuelle_entity(libelle="Autre formule existante")
        mock_repo = MagicMock()
        mock_repo.get_by_id.return_value = existing
        mock_repo.find_by_company_and_libelle.return_value = other
        mock_repo.update.return_value = None

        with patch(
            "app.modules.mutuelle_types.application.commands.SupabaseMutuelleTypeRepository",
            return_value=mock_repo,
        ):
            with pytest.raises(HTTPException) as exc_info:
                update_mutuelle_type(MUTUELLE_ID, COMPANY_ID, USER_ID, payload)

        assert exc_info.value.status_code == 400
        assert "Autre formule existante" in str(exc_info.value.detail)


class TestDeleteMutuelleType:
    """Commande delete_mutuelle_type."""

    def test_delete_mutuelle_type_success_returns_status(self):
        existing = _make_mutuelle_entity(
            company_id=UUID(COMPANY_ID), libelle="À supprimer"
        )
        mock_repo = MagicMock()
        mock_repo.get_by_id.return_value = existing
        mock_repo.list_employee_ids.return_value = ["emp-1"]
        mock_repo.remove_employee_associations_and_sync_specificites.return_value = None
        mock_repo.delete.return_value = True

        with patch(
            "app.modules.mutuelle_types.application.commands.SupabaseMutuelleTypeRepository",
            return_value=mock_repo,
        ):
            result = delete_mutuelle_type(MUTUELLE_ID, COMPANY_ID)

        mock_repo.get_by_id.assert_called_once_with(MUTUELLE_ID, COMPANY_ID)
        mock_repo.list_employee_ids.assert_called_once_with(MUTUELLE_ID)
        mock_repo.remove_employee_associations_and_sync_specificites.assert_called_once_with(
            MUTUELLE_ID, ["emp-1"]
        )
        mock_repo.delete.assert_called_once_with(MUTUELLE_ID)
        assert result["status"] == "success"
        assert "supprimée" in result["message"].lower()

    def test_delete_mutuelle_type_not_found_raises_404(self):
        mock_repo = MagicMock()
        mock_repo.get_by_id.return_value = None

        with patch(
            "app.modules.mutuelle_types.application.commands.SupabaseMutuelleTypeRepository",
            return_value=mock_repo,
        ):
            with pytest.raises(HTTPException) as exc_info:
                delete_mutuelle_type(MUTUELLE_ID, COMPANY_ID)

        assert exc_info.value.status_code == 404
        mock_repo.delete.assert_not_called()

    def test_delete_mutuelle_type_wrong_company_raises_403(self):
        existing = _make_mutuelle_entity(company_id=uuid4())  # différent de COMPANY_ID
        mock_repo = MagicMock()
        mock_repo.get_by_id.return_value = existing

        with patch(
            "app.modules.mutuelle_types.application.commands.SupabaseMutuelleTypeRepository",
            return_value=mock_repo,
        ):
            with pytest.raises(HTTPException) as exc_info:
                delete_mutuelle_type(MUTUELLE_ID, COMPANY_ID)

        assert exc_info.value.status_code == 403
        mock_repo.delete.assert_not_called()
