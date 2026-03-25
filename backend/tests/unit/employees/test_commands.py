"""
Tests unitaires des commandes du module employees (create, update, delete).

Repositories et providers mockés. Pas d'accès DB ni HTTP.
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.modules.employees.application.commands import (
    create_employee,
    delete_employee,
    update_employee,
)


pytestmark = pytest.mark.unit


def _minimal_employee_data():
    return {
        "first_name": "Jean",
        "last_name": "Dupont",
        "email": "jean.dupont@example.com",
        "job_title": "Dev",
        "nir": "1 90 05 49 588 157 75",
        "date_naissance": "1990-05-15",
        "lieu_naissance": "Paris",
        "nationalite": "Française",
        "adresse": {"rue": "1 rue Test", "ville": "Paris", "code_postal": "75001"},
        "coordonnees_bancaires": {
            "iban": "FR7612345678901234567890123",
            "bic": "BNPAFRPP",
        },
        "hire_date": "2024-01-01",
        "contract_type": "CDI",
        "statut": "actif",
        "is_temps_partiel": False,
        "duree_hebdomadaire": 35.0,
        "salaire_de_base": {"montant": 3000},
        "classification_conventionnelle": {},
        "specificites_paie": {},
    }


@patch("app.modules.employees.application.commands.on_rib_submitted")
@patch("app.modules.employees.application.commands.generate_credentials_pdf")
@patch("app.modules.employees.application.commands.prepare_employee_insert_data")
@patch("app.modules.employees.application.commands._profile_repository")
@patch("app.modules.employees.application.commands._employee_repository")
@patch("app.modules.employees.application.commands.get_auth_provider")
@patch("app.modules.employees.application.commands.get_storage_provider")
@patch("app.modules.employees.application.commands.get_company_reader")
@pytest.mark.asyncio
async def test_create_employee_success_returns_employee_with_generated_password(
    mock_get_company_reader,
    mock_get_storage,
    mock_get_auth,
    mock_emp_repo,
    mock_profile_repo,
    mock_prepare_insert,
    mock_gen_credentials_pdf,
    mock_on_rib_submitted,
):
    """create_employee : succès, retourne l'employé avec generated_password."""
    auth = MagicMock()
    auth.create_user.return_value = "user-uuid-123"
    mock_get_auth.return_value = auth
    mock_get_storage.return_value = MagicMock()
    mock_get_company_reader.return_value = MagicMock()
    mock_prepare_insert.return_value = {
        "id": "user-uuid-123",
        "first_name": "Jean",
        "last_name": "Dupont",
    }
    mock_emp_repo.create.return_value = {
        "id": "user-uuid-123",
        "first_name": "Jean",
        "last_name": "Dupont",
        "email": "jean.dupont@example.com",
    }
    mock_profile_repo.upsert.return_value = {}
    mock_gen_credentials_pdf.return_value = b"pdf-content"
    mock_on_rib_submitted.return_value = []

    result = await create_employee(
        employee_data=_minimal_employee_data(),
        company_id="company-1",
    )

    assert result["id"] == "user-uuid-123"
    assert "generated_password" in result
    assert len(result["generated_password"]) == 12
    auth.create_user.assert_called_once()
    mock_profile_repo.upsert.assert_called_once()
    mock_emp_repo.create.assert_called_once()
    mock_prepare_insert.assert_called_once()


@patch("app.modules.employees.application.commands.get_auth_provider")
@pytest.mark.asyncio
async def test_create_employee_auth_failure_raises_400(mock_get_auth):
    """create_employee : si Auth échoue (ex. email déjà utilisé) → HTTP 400."""
    auth = MagicMock()
    auth.create_user.side_effect = RuntimeError("Email already exists")
    mock_get_auth.return_value = auth

    with pytest.raises(HTTPException) as exc_info:
        await create_employee(
            employee_data=_minimal_employee_data(),
            company_id="company-1",
        )
    assert exc_info.value.status_code == 400
    assert (
        "email" in (exc_info.value.detail or "").lower()
        or "utilisateur" in (exc_info.value.detail or "").lower()
    )


@patch("app.modules.employees.application.commands.on_rib_submitted")
@patch("app.modules.employees.application.commands.generate_credentials_pdf")
@patch("app.modules.employees.application.commands.prepare_employee_insert_data")
@patch("app.modules.employees.application.commands._profile_repository")
@patch("app.modules.employees.application.commands._employee_repository")
@patch("app.modules.employees.application.commands.get_auth_provider")
@patch("app.modules.employees.application.commands.get_storage_provider")
@patch("app.modules.employees.application.commands.get_company_reader")
@pytest.mark.asyncio
async def test_create_employee_profile_upsert_failure_rollback_auth(
    mock_get_company_reader,
    mock_get_storage,
    mock_get_auth,
    mock_emp_repo,
    mock_profile_repo,
    mock_prepare_insert,
    mock_gen_credentials_pdf,
    mock_on_rib_submitted,
):
    """create_employee : si upsert profil échoue, on supprime l'utilisateur Auth (rollback)."""
    auth = MagicMock()
    auth.create_user.return_value = "user-uuid-456"
    mock_get_auth.return_value = auth
    mock_get_storage.return_value = MagicMock()
    mock_get_company_reader.return_value = MagicMock()
    mock_prepare_insert.return_value = {}
    mock_profile_repo.upsert.side_effect = RuntimeError("Profile insert failed")
    mock_on_rib_submitted.return_value = []

    with pytest.raises(HTTPException) as exc_info:
        await create_employee(
            employee_data=_minimal_employee_data(),
            company_id="company-1",
        )
    assert exc_info.value.status_code == 500
    # Rollback : delete_user doit être appelé (au moins une fois) pour supprimer l'utilisateur Auth créé
    auth.delete_user.assert_any_call("user-uuid-456")


@patch("app.modules.employees.application.commands._employee_repository")
def test_update_employee_success_returns_updated_data(mock_emp_repo):
    """update_employee : succès, retourne les données mises à jour."""
    mock_emp_repo.get_by_id_only.return_value = {
        "id": "emp-1",
        "company_id": "company-1",
        "first_name": "Jean",
        "last_name": "Dupont",
        "coordonnees_bancaires": {},
    }
    mock_emp_repo.update.return_value = {
        "id": "emp-1",
        "first_name": "Jean",
        "last_name": "Dupont",
        "phone_number": "+33600000000",
    }
    result = update_employee("emp-1", {"phone_number": "+33600000000"})
    assert result["phone_number"] == "+33600000000"
    mock_emp_repo.update.assert_called_once_with(
        "emp-1", {"phone_number": "+33600000000"}
    )


@patch("app.modules.employees.application.commands._employee_repository")
def test_update_employee_not_found_raises_404(mock_emp_repo):
    """update_employee : employé non trouvé ou pas de donnée modifiée → 404."""
    mock_emp_repo.update.return_value = None
    with pytest.raises(HTTPException) as exc_info:
        update_employee("unknown-id", {"first_name": "Paul"})
    assert exc_info.value.status_code == 404


@patch("app.modules.employees.application.commands.get_auth_provider")
@patch("app.modules.employees.application.commands._employee_repository")
def test_delete_employee_success_calls_repo_and_auth(mock_emp_repo, mock_get_auth):
    """delete_employee : appelle repository.delete puis auth.delete_user."""
    auth = MagicMock()
    mock_get_auth.return_value = auth
    mock_emp_repo.delete.return_value = True
    delete_employee("emp-1")
    mock_emp_repo.delete.assert_called_once_with("emp-1")
    auth.delete_user.assert_called_once_with("emp-1")


@patch("app.modules.employees.application.commands.get_auth_provider")
@patch("app.modules.employees.application.commands._employee_repository")
def test_delete_employee_user_not_found_raises_404(mock_emp_repo, mock_get_auth):
    """delete_employee : si Auth renvoie User not found → 404."""
    auth = MagicMock()
    auth.delete_user.side_effect = Exception("User not found")
    mock_get_auth.return_value = auth
    mock_emp_repo.delete.return_value = True
    with pytest.raises(HTTPException) as exc_info:
        delete_employee("emp-1")
    assert exc_info.value.status_code == 404
