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
    upload_employee_contract,
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


@patch("app.modules.employees.application.commands._grant_collaborator_company_access")
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
    mock_grant_access,
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
        granted_by_user_id="rh-user-1",
    )

    assert result["id"] == "user-uuid-123"
    assert "generated_password" in result
    assert len(result["generated_password"]) == 12
    auth.create_user.assert_called_once()
    mock_profile_repo.upsert.assert_called_once()
    mock_emp_repo.create.assert_called_once()
    mock_prepare_insert.assert_called_once()
    mock_grant_access.assert_called_once_with(
        "user-uuid-123", "company-1", "rh-user-1"
    )


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
def test_update_employee_merges_specificites_paie(mock_emp_repo):
    """update_employee : fusionne specificites_paie sans écraser les autres clés."""
    mock_emp_repo.get_by_id_only.return_value = {
        "id": "emp-1",
        "specificites_paie": {
            "mutuelle": {"adhesion": True},
            "prelevement_a_la_source": {"is_personnalise": False, "taux": 0},
        },
    }
    mock_emp_repo.update.return_value = {"id": "emp-1"}
    mock_emp_repo.get_by_id_only.side_effect = [
        mock_emp_repo.get_by_id_only.return_value,
        {
            "id": "emp-1",
            "employment_status": "actif",
            "specificites_paie": {
                "mutuelle": {"adhesion": True},
                "prelevement_a_la_source": {"is_personnalise": True, "taux": 12.5},
            },
            "nir": "1850574001234",
            "date_naissance": "1985-05-01",
            "adresse": {"rue": "1 rue Test"},
            "coordonnees_bancaires": {"iban": "FR7612345678901234567890123"},
            "salaire_de_base": {"valeur": 2500},
        },
        {
            "id": "emp-1",
            "specificites_paie": {
                "mutuelle": {"adhesion": True},
                "prelevement_a_la_source": {"is_personnalise": True, "taux": 12.5},
            },
            "employment_status": "actif",
            "nir": "1850574001234",
            "date_naissance": "1985-05-01",
            "adresse": {"rue": "1 rue Test"},
            "coordonnees_bancaires": {"iban": "FR7612345678901234567890123"},
            "salaire_de_base": {"valeur": 2500},
        },
    ]

    update_employee(
        "emp-1",
        {
            "specificites_paie": {
                "prelevement_a_la_source": {"is_personnalise": True, "taux": 12.5},
            },
        },
    )

    mock_emp_repo.update.assert_called_once_with(
        "emp-1",
        {
            "specificites_paie": {
                "mutuelle": {"adhesion": True},
                "prelevement_a_la_source": {"is_personnalise": True, "taux": 12.5},
            },
        },
    )


@patch("app.modules.employees.application.commands._employee_repository")
def test_update_employee_success_returns_updated_data(mock_emp_repo):
    """update_employee : succès, retourne les données mises à jour."""
    mock_emp_repo.get_by_id_only.return_value = {
        "id": "emp-1",
        "company_id": "company-1",
        "first_name": "Jean",
        "last_name": "Dupont",
        "phone_number": "+33600000000",
        "coordonnees_bancaires": {"iban": "FR7612345678901234567890123", "bic": "BNPAFRPP"},
        "employment_status": "actif",
        "nir": "1850574001234",
        "date_naissance": "1985-05-01",
        "adresse": {"rue": "1 rue Test"},
        "salaire_de_base": {"valeur": 2500},
    }
    mock_emp_repo.update.return_value = {
        "id": "emp-1",
        "first_name": "Jean",
        "last_name": "Dupont",
        "phone_number": "+33600000000",
    }
    result = update_employee("emp-1", {"phone_number": "+33600000000"})
    assert result["phone_number"] == "+33600000000"
    assert result["profile_complete"] is True
    assert result["missing_payroll_fields"] == []
    mock_emp_repo.update.assert_called_once_with(
        "emp-1", {"phone_number": "+33600000000"}
    )


@patch("app.modules.employees.application.commands.is_profile_complete")
@patch("app.modules.employees.application.commands._employee_repository")
def test_update_employee_completes_onboarding_and_activates(
    mock_emp_repo, mock_is_complete
):
    """update_employee : fiche paie complète + en_onboarding → passage en actif."""
    mock_emp_repo.update.return_value = {"id": "emp-1"}
    complete_employee = {
        "id": "emp-1",
        "employment_status": "en_onboarding",
        "nir": "1850574001234",
        "date_naissance": "1985-05-01",
        "adresse": {"rue": "1 rue Test", "ville": "Paris"},
        "coordonnees_bancaires": {"iban": "FR7612345678901234567890123"},
        "salaire_de_base": {"valeur": 2500},
    }
    activated_employee = {
        **complete_employee,
        "employment_status": "actif",
    }
    mock_emp_repo.get_by_id_only.side_effect = [
        complete_employee,  # alertes RIB
        complete_employee,  # _maybe_activate_after_onboarding
        activated_employee,  # refresh final
    ]
    mock_is_complete.return_value = True

    result = update_employee(
        "emp-1",
        {
            "nir": "1850574001234",
            "date_naissance": "1985-05-01",
            "adresse": {"rue": "1 rue Test", "ville": "Paris"},
            "coordonnees_bancaires": {"iban": "FR7612345678901234567890123"},
            "salaire_de_base": {"valeur": 2500},
        },
    )

    mock_emp_repo.update.assert_any_call("emp-1", {"employment_status": "actif"})
    assert result["employment_status"] == "actif"
    assert result["profile_complete"] is True


@patch("app.modules.employees.application.commands._employee_repository")
def test_update_employee_contract_and_specificites_paie(mock_emp_repo):
    """update_employee : champs contrat et specificites_paie persistés."""
    mock_emp_repo.get_by_id_only.return_value = {
        "id": "emp-1",
        "company_id": "company-1",
        "employment_status": "actif",
        "nir": "1850574001234",
        "date_naissance": "1985-05-01",
        "adresse": {"rue": "1 rue Test", "ville": "Paris"},
        "coordonnees_bancaires": {"iban": "FR7612345678901234567890123"},
        "salaire_de_base": {"valeur": 2500},
        "specificites_paie": {"is_alsace_moselle": False},
    }
    mock_emp_repo.update.return_value = {"id": "emp-1", "job_title": "Dev senior"}
    update_data = {
        "job_title": "Dev senior",
        "statut": "Cadre",
        "duree_hebdomadaire": 39.0,
        "classification_conventionnelle": {
            "groupe_emploi": "C",
            "classe_emploi": 6,
            "coefficient": 240,
        },
        "team_id": "team-1",
        "specificites_paie": {
            "is_alsace_moselle": False,
            "mutuelle": {"adhesion": True, "mutuelle_type_ids": ["mut-1"]},
        },
    }
    result = update_employee("emp-1", update_data)
    mock_emp_repo.update.assert_called_with("emp-1", update_data)
    assert result["profile_complete"] is True


@patch("app.modules.employees.application.commands._employee_repository")
def test_update_employee_nir_duplicate_raises_400(mock_emp_repo):
    """update_employee : NIR déjà enregistré → HTTP 400."""
    mock_emp_repo.get_by_id_only.return_value = {
        "id": "emp-1",
        "company_id": "company-1",
        "coordonnees_bancaires": {},
    }
    mock_emp_repo.update.side_effect = Exception(
        'duplicate key value violates unique constraint "employees_nir_key"'
    )

    with pytest.raises(HTTPException) as exc_info:
        update_employee("emp-1", {"nir": "1850574001234"})
    assert exc_info.value.status_code == 400
    assert "sécurité sociale" in (exc_info.value.detail or "").lower()


@patch("app.modules.employees.application.commands._employee_repository")
def test_update_employee_not_found_raises_404(mock_emp_repo):
    """update_employee : employé non trouvé ou pas de donnée modifiée → 404."""
    mock_emp_repo.update.return_value = None
    with pytest.raises(HTTPException) as exc_info:
        update_employee("unknown-id", {"first_name": "Paul"})
    assert exc_info.value.status_code == 404


@patch("app.modules.users.application.service.get_user_repository")
@patch("app.modules.users.application.service.get_user_permission_repository")
@patch("app.modules.users.application.service.get_user_company_access_repository")
@patch("app.modules.employees.application.commands.get_auth_provider")
@patch("app.modules.employees.application.commands._employee_repository")
def test_delete_employee_success_calls_repo_and_auth(
    mock_emp_repo,
    mock_get_auth,
    mock_get_access_repo,
    mock_get_perm_repo,
    mock_get_user_repo,
):
    """delete_employee : nettoie accès/permissions/profil, delete employee puis auth."""
    auth = MagicMock()
    mock_get_auth.return_value = auth
    mock_emp_repo.get_by_id_only.return_value = {"id": "emp-1", "company_id": "c1"}
    mock_emp_repo.delete.return_value = True

    access_repo = MagicMock()
    access_repo.get_accesses_for_user.return_value = [{"company_id": "c1"}]
    mock_get_access_repo.return_value = access_repo
    perm_repo = MagicMock()
    mock_get_perm_repo.return_value = perm_repo
    user_repo = MagicMock()
    mock_get_user_repo.return_value = user_repo

    delete_employee("emp-1")

    mock_emp_repo.get_by_id_only.assert_called_once_with("emp-1")
    perm_repo.delete_for_user_company.assert_called_once_with("emp-1", "c1")
    access_repo.delete.assert_called_once_with("emp-1", "c1")
    user_repo.delete.assert_called_once_with("emp-1")
    mock_emp_repo.delete.assert_called_once_with("emp-1")
    auth.delete_user.assert_called_once_with("emp-1")


@patch("app.modules.users.application.service.get_user_repository")
@patch("app.modules.users.application.service.get_user_permission_repository")
@patch("app.modules.users.application.service.get_user_company_access_repository")
@patch("app.modules.employees.application.commands.get_auth_provider")
@patch("app.modules.employees.application.commands._employee_repository")
def test_delete_employee_uses_user_id_when_set(
    mock_emp_repo,
    mock_get_auth,
    mock_get_access_repo,
    mock_get_perm_repo,
    mock_get_user_repo,
):
    """delete_employee : auth_uid = employees.user_id si présent."""
    auth = MagicMock()
    mock_get_auth.return_value = auth
    mock_emp_repo.get_by_id_only.return_value = {
        "id": "row-id",
        "user_id": "auth-uid",
        "company_id": "c1",
    }
    mock_emp_repo.delete.return_value = True
    access_repo = MagicMock()
    access_repo.get_accesses_for_user.return_value = [{"company_id": "c1"}]
    mock_get_access_repo.return_value = access_repo
    mock_get_perm_repo.return_value = MagicMock()
    mock_get_user_repo.return_value = MagicMock()

    delete_employee("row-id")

    access_repo.get_accesses_for_user.assert_called_once_with("auth-uid")
    auth.delete_user.assert_called_once_with("auth-uid")
    mock_emp_repo.delete.assert_called_once_with("row-id")


@patch("app.modules.users.application.service.get_user_repository")
@patch("app.modules.users.application.service.get_user_permission_repository")
@patch("app.modules.users.application.service.get_user_company_access_repository")
@patch("app.modules.employees.application.commands.get_auth_provider")
@patch("app.modules.employees.application.commands._employee_repository")
def test_delete_employee_user_not_found_auth_ok(
    mock_emp_repo,
    mock_get_auth,
    mock_get_access_repo,
    mock_get_perm_repo,
    mock_get_user_repo,
):
    """delete_employee : Auth « user not found » après nettoyage → succès (idempotent)."""
    auth = MagicMock()
    auth.delete_user.side_effect = Exception("User not found")
    mock_get_auth.return_value = auth
    mock_emp_repo.get_by_id_only.return_value = {"id": "emp-1"}
    mock_emp_repo.delete.return_value = True
    mock_get_access_repo.return_value = MagicMock(
        get_accesses_for_user=MagicMock(return_value=[])
    )
    mock_get_perm_repo.return_value = MagicMock()
    mock_get_user_repo.return_value = MagicMock()

    delete_employee("emp-1")

    mock_emp_repo.delete.assert_called_once_with("emp-1")


@patch("app.modules.employees.application.commands._employee_repository")
def test_delete_employee_not_found_raises_404(mock_emp_repo):
    """delete_employee : employé absent → 404."""
    mock_emp_repo.get_by_id_only.return_value = None
    with pytest.raises(HTTPException) as exc_info:
        delete_employee("missing")
    assert exc_info.value.status_code == 404


@patch("app.modules.employees.application.commands.get_storage_provider")
@patch("app.modules.employees.application.commands._employee_repository")
def test_upload_employee_contract_success(mock_emp_repo, mock_get_storage):
    """upload_employee_contract : dépose le PDF dans le storage."""
    mock_emp_repo.get_by_id.return_value = {"id": "emp-1"}
    storage = MagicMock()
    mock_get_storage.return_value = storage

    upload_employee_contract(
        employee_id="emp-1",
        company_id="company-1",
        file_content=b"%PDF-1.4 test",
        content_type="application/pdf",
    )

    mock_emp_repo.get_by_id.assert_called_once_with("emp-1", "company-1")
    storage.upload.assert_called_once_with(
        "contracts",
        "company-1/emp-1/contrat.pdf",
        b"%PDF-1.4 test",
        "application/pdf",
    )


@patch("app.modules.employees.application.commands.is_profile_complete")
@patch("app.modules.employees.application.commands.get_storage_provider")
@patch("app.modules.employees.application.commands._employee_repository")
def test_upload_employee_contract_activates_when_onboarding_complete(
    mock_emp_repo, mock_get_storage, mock_is_complete
):
    """Dépôt du contrat : si fiche paie complète et statut en_onboarding → actif."""
    mock_emp_repo.get_by_id.return_value = {"id": "emp-1"}
    mock_emp_repo.get_by_id_only.return_value = {
        "id": "emp-1",
        "employment_status": "en_onboarding",
    }
    mock_is_complete.return_value = True
    mock_get_storage.return_value = MagicMock()

    upload_employee_contract(
        employee_id="emp-1",
        company_id="company-1",
        file_content=b"%PDF-1.4 test",
        content_type="application/pdf",
    )

    mock_emp_repo.update.assert_called_once_with(
        "emp-1", {"employment_status": "actif"}
    )


@patch("app.modules.employees.application.commands.is_profile_complete")
@patch("app.modules.employees.application.commands.get_storage_provider")
@patch("app.modules.employees.application.commands._employee_repository")
def test_upload_employee_contract_no_activation_when_not_onboarding(
    mock_emp_repo, mock_get_storage, mock_is_complete
):
    """Dépôt du contrat : salarié déjà actif → pas de changement de statut."""
    mock_emp_repo.get_by_id.return_value = {"id": "emp-1"}
    mock_emp_repo.get_by_id_only.return_value = {
        "id": "emp-1",
        "employment_status": "actif",
    }
    mock_is_complete.return_value = True
    mock_get_storage.return_value = MagicMock()

    upload_employee_contract(
        employee_id="emp-1",
        company_id="company-1",
        file_content=b"%PDF-1.4 test",
        content_type="application/pdf",
    )

    mock_emp_repo.update.assert_not_called()


@patch("app.modules.employees.application.commands._employee_repository")
def test_upload_employee_contract_empty_file_raises_400(mock_emp_repo):
    """upload_employee_contract : fichier vide → 400."""
    with pytest.raises(HTTPException) as exc_info:
        upload_employee_contract(
            employee_id="emp-1",
            company_id="company-1",
            file_content=b"",
        )
    assert exc_info.value.status_code == 400
    mock_emp_repo.get_by_id.assert_not_called()


@patch("app.modules.employees.application.commands._employee_repository")
def test_upload_employee_contract_not_found_raises_404(mock_emp_repo):
    """upload_employee_contract : employé absent → 404."""
    mock_emp_repo.get_by_id.return_value = None
    with pytest.raises(HTTPException) as exc_info:
        upload_employee_contract(
            employee_id="missing",
            company_id="company-1",
            file_content=b"%PDF-1.4",
        )
    assert exc_info.value.status_code == 404
