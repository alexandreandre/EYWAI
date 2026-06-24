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


@patch("app.modules.employees.application.commands.allocate_collaborator_username", return_value="jean.dupont")
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
    mock_allocate_username,
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


@patch("app.modules.employees.application.commands.allocate_collaborator_username", return_value="jean.dupont")
@patch("app.modules.employees.application.commands.get_auth_provider")
@pytest.mark.asyncio
async def test_create_employee_auth_failure_raises_400(
    mock_get_auth, mock_allocate_username
):
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


@patch("app.modules.employees.application.commands.allocate_collaborator_username", return_value="jean.dupont")
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
    mock_allocate_username,
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


@patch("app.modules.employees.application.commands._employee_repository")
def test_update_employee_persists_periode_essai(mock_emp_repo):
    """update_employee : persiste periode_essai jsonb."""
    mock_emp_repo.get_by_id_only.return_value = {
        "id": "emp-1",
        "company_id": "company-1",
        "employment_status": "en_onboarding",
        "hire_date": "2026-01-15",
        "nir": "1850574001234",
        "date_naissance": "1985-05-01",
        "adresse": {"rue": "1 rue Test"},
        "coordonnees_bancaires": {"iban": "FR7612545678901234567890123"},
        "salaire_de_base": {"valeur": 2500},
    }
    periode_essai = {
        "duree_initiale": 2,
        "unite": "mois",
        "renouvellement_possible": True,
        "statut": "en_cours",
    }
    mock_emp_repo.update.return_value = {"id": "emp-1", "periode_essai": periode_essai}

    result = update_employee("emp-1", {"periode_essai": periode_essai})

    mock_emp_repo.update.assert_any_call("emp-1", {"periode_essai": periode_essai})
    assert result["id"] == "emp-1"


@patch("app.modules.employees.application.commands._employee_repository")
def test_update_employee_clears_periode_essai(mock_emp_repo):
    """update_employee : periode_essai null désactive le suivi."""
    mock_emp_repo.get_by_id_only.return_value = {
        "id": "emp-1",
        "company_id": "company-1",
        "employment_status": "actif",
        "nir": "1850574001234",
        "date_naissance": "1985-05-01",
        "adresse": {"rue": "1 rue Test"},
        "coordonnees_bancaires": {"iban": "FR7612545678901234567890123"},
        "salaire_de_base": {"valeur": 2500},
    }
    mock_emp_repo.update.return_value = {"id": "emp-1", "periode_essai": None}

    update_employee("emp-1", {"periode_essai": None})

    mock_emp_repo.update.assert_called_with("emp-1", {"periode_essai": None})


@patch("app.modules.employees.application.deletion_cleanup.cleanup_user_account_for_company")
@patch("app.modules.employees.application.deletion_cleanup.cleanup_employee_orphan_rows")
@patch("app.modules.employees.application.deletion_cleanup.cleanup_employee_storage")
@patch("app.modules.employees.application.commands.get_auth_provider")
@patch("app.modules.employees.application.commands._employee_repository")
def test_delete_employee_success_calls_repo_and_auth(
    mock_emp_repo,
    mock_get_auth,
    mock_cleanup_storage,
    mock_cleanup_orphans,
    mock_cleanup_user,
):
    """delete_employee : nettoie données, supprime la ligne puis Auth si orphelin."""
    auth = MagicMock()
    mock_get_auth.return_value = auth
    mock_emp_repo.get_by_id.return_value = {"id": "emp-1", "company_id": "c1"}
    mock_emp_repo.delete.return_value = True
    mock_cleanup_user.return_value = True

    delete_employee("emp-1", "c1")

    mock_emp_repo.get_by_id.assert_called_once_with("emp-1", "c1")
    mock_cleanup_storage.assert_called_once_with("c1", "emp-1")
    mock_cleanup_orphans.assert_called_once_with("emp-1")
    mock_cleanup_user.assert_called_once_with("emp-1", "c1", "emp-1")
    mock_emp_repo.delete.assert_called_once_with("emp-1")
    auth.delete_user.assert_called_once_with("emp-1")


@patch("app.modules.employees.application.deletion_cleanup.cleanup_user_account_for_company")
@patch("app.modules.employees.application.deletion_cleanup.cleanup_employee_orphan_rows")
@patch("app.modules.employees.application.deletion_cleanup.cleanup_employee_storage")
@patch("app.modules.employees.application.commands.get_auth_provider")
@patch("app.modules.employees.application.commands._employee_repository")
def test_delete_employee_uses_user_id_when_set(
    mock_emp_repo,
    mock_get_auth,
    _mock_storage,
    _mock_orphans,
    mock_cleanup_user,
):
    """delete_employee : auth_uid = employees.user_id si présent."""
    auth = MagicMock()
    mock_get_auth.return_value = auth
    mock_emp_repo.get_by_id.return_value = {
        "id": "row-id",
        "user_id": "auth-uid",
        "company_id": "c1",
    }
    mock_emp_repo.delete.return_value = True
    mock_cleanup_user.return_value = True

    delete_employee("row-id", "c1")

    mock_cleanup_user.assert_called_once_with("auth-uid", "c1", "row-id")
    auth.delete_user.assert_called_once_with("auth-uid")
    mock_emp_repo.delete.assert_called_once_with("row-id")


@patch("app.modules.employees.application.deletion_cleanup.cleanup_user_account_for_company")
@patch("app.modules.employees.application.deletion_cleanup.cleanup_employee_orphan_rows")
@patch("app.modules.employees.application.deletion_cleanup.cleanup_employee_storage")
@patch("app.modules.employees.application.commands.get_auth_provider")
@patch("app.modules.employees.application.commands._employee_repository")
def test_delete_employee_user_not_found_auth_ok(
    mock_emp_repo,
    mock_get_auth,
    _mock_storage,
    _mock_orphans,
    mock_cleanup_user,
):
    """delete_employee : Auth « user not found » après nettoyage → succès (idempotent)."""
    auth = MagicMock()
    auth.delete_user.side_effect = Exception("User not found")
    mock_get_auth.return_value = auth
    mock_emp_repo.get_by_id.return_value = {"id": "emp-1", "company_id": "c1"}
    mock_emp_repo.delete.return_value = True
    mock_cleanup_user.return_value = True

    delete_employee("emp-1", "c1")

    mock_emp_repo.delete.assert_called_once_with("emp-1")


@patch("app.modules.employees.application.deletion_cleanup.cleanup_user_account_for_company")
@patch("app.modules.employees.application.deletion_cleanup.cleanup_employee_orphan_rows")
@patch("app.modules.employees.application.deletion_cleanup.cleanup_employee_storage")
@patch("app.modules.employees.application.commands._employee_repository")
def test_delete_employee_skips_auth_when_user_retained(
    mock_emp_repo,
    _mock_storage,
    _mock_orphans,
    mock_cleanup_user,
):
    """delete_employee : ne supprime pas Auth si le compte est conservé."""
    mock_emp_repo.get_by_id.return_value = {
        "id": "emp-1",
        "user_id": "auth-uid",
        "company_id": "c1",
    }
    mock_cleanup_user.return_value = False

    with patch("app.modules.employees.application.commands.get_auth_provider") as mock_auth:
        delete_employee("emp-1", "c1")
        mock_auth.return_value.delete_user.assert_not_called()


@patch("app.modules.employees.application.commands._employee_repository")
def test_delete_employee_not_found_raises_404(mock_emp_repo):
    """delete_employee : employé absent → 404."""
    mock_emp_repo.get_by_id.return_value = None
    with pytest.raises(HTTPException) as exc_info:
        delete_employee("missing", "c1")
    assert exc_info.value.status_code == 404


@patch("app.modules.employees.application.deletion_cleanup.cleanup_user_account_for_company")
@patch("app.modules.employees.application.deletion_cleanup.cleanup_employee_orphan_rows")
@patch("app.modules.employees.application.deletion_cleanup.cleanup_employee_storage")
@patch("app.modules.employees.application.commands._employee_repository")
def test_delete_employee_maps_fk_error_to_409(
    mock_emp_repo,
    _mock_storage,
    _mock_orphans,
    _mock_cleanup_user,
):
    """delete_employee : erreur FK → 409 message français."""
    mock_emp_repo.get_by_id.return_value = {"id": "emp-1", "company_id": "c1"}
    mock_emp_repo.delete.side_effect = Exception(
        '{"code":"23503","message":"violates foreign key constraint"}'
    )
    with pytest.raises(HTTPException) as exc_info:
        delete_employee("emp-1", "c1")
    assert exc_info.value.status_code == 409
    assert "données liées" in exc_info.value.detail


@patch("app.modules.employees.application.commands._iter_employee_deletion")
@patch("app.modules.employees.application.commands._employee_repository")
@patch("app.core.database.supabase")
def test_delete_all_company_employees_success(
    mock_supabase,
    mock_emp_repo,
    mock_iter_deletion,
):
    """delete_all_company_employees : supprime chaque employé de l'entreprise."""
    from app.modules.employees.application.commands import delete_all_company_employees

    mock_supabase.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
        data={"id": "c1", "company_name": "Acme"}
    )
    mock_emp_repo.get_by_company.return_value = [
        {"id": "emp-1", "first_name": "Alice", "last_name": "Martin"},
        {"id": "emp-2", "first_name": "Bob", "last_name": "Durand"},
    ]
    mock_iter_deletion.return_value = iter(
        [{"event": "step", "step": "finalize", "label": "Terminé"}]
    )

    result = delete_all_company_employees("c1")

    assert result["success"] is True
    assert result["requested_count"] == 2
    assert result["removed_count"] == 2
    assert len(result["failed"]) == 0
    assert mock_iter_deletion.call_count == 2


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


@patch("app.modules.employees.application.credentials_pdf.store_credentials_pdf_for_employee")
@patch("app.modules.employees.application.commands._grant_collaborator_company_access")
@patch("app.modules.employees.application.commands.update_employee")
@patch("app.modules.employees.application.commands.allocate_collaborator_username")
@patch("app.modules.employees.application.commands._profile_repository")
@patch("app.modules.employees.application.commands.get_auth_provider")
@patch("app.modules.employees.application.commands._employee_repository")
def test_activate_imported_employee_account_generates_credentials_pdf(
    mock_emp_repo: MagicMock,
    mock_auth_provider: MagicMock,
    mock_profile_repo: MagicMock,
    mock_allocate_username: MagicMock,
    mock_update_employee: MagicMock,
    mock_grant_access: MagicMock,
    mock_store_pdf: MagicMock,
) -> None:
    from app.modules.employees.application.commands import activate_imported_employee_account

    mock_emp_repo.get_by_id.return_value = {
        "id": "emp-1",
        "first_name": "Jean",
        "last_name": "MARTIN",
        "job_title": "Dev",
        "username": None,
        "user_id": None,
    }
    auth = MagicMock()
    auth.create_user.return_value = "user-1"
    mock_auth_provider.return_value = auth
    mock_allocate_username.return_value = "jean.martin"
    mock_store_pdf.return_value = "company-1/emp-1/creation_compte.pdf"

    result = activate_imported_employee_account(
        "emp-1",
        "company-1",
        "jean.martin@test.fr",
        granted_by_user_id="admin-1",
    )

    assert result["credentials_pdf_path"] == "company-1/emp-1/creation_compte.pdf"
    mock_store_pdf.assert_called_once()
    assert mock_store_pdf.call_args.args == ("emp-1", "company-1")
    assert mock_store_pdf.call_args.kwargs["username"] == "jean.martin"
    assert mock_store_pdf.call_args.kwargs["password"] == result["generated_password"]
