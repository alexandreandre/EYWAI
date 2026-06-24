"""Tests salarié importé sans Auth."""

from unittest.mock import patch
import uuid

import pytest

from app.modules.employees.application.commands import create_employee_imported


@pytest.fixture
def employee_payload():
    return {
        "first_name": "Jean",
        "last_name": "MARTIN",
        "email": "jean.martin@test.local",
        "nir": "180032710123448",
        "date_naissance": "1990-01-01",
        "lieu_naissance": "Paris",
        "nationalite": "Française",
        "adresse": {"rue": "1 rue Test", "code_postal": "75001", "ville": "Paris"},
        "coordonnees_bancaires": {"iban": "", "bic": ""},
        "hire_date": "2020-03-15",
        "contract_type": "CDI",
        "statut": "Cadre",
        "job_title": "Dev",
        "is_temps_partiel": False,
        "duree_hebdomadaire": 35.0,
        "salaire_de_base": {"valeur": 3500, "type": "mensuel"},
        "classification_conventionnelle": {},
        "elements_variables": {},
        "specificites_paie": {"mutuelle": {"adhesion": False}, "prevoyance": {"adhesion": False}},
        "employment_status": "actif",
    }


def test_create_employee_imported_no_auth(employee_payload):
    company_id = str(uuid.uuid4())
    with patch(
        "app.modules.employees.application.commands.allocate_collaborator_username",
        return_value="jean.martin",
    ), patch(
        "app.modules.employees.application.credentials_pdf.store_credentials_pdf_for_employee"
    ) as mock_store_pdf, patch(
        "app.modules.employees.application.commands._employee_repository"
    ) as repo:
        repo.create.return_value = {
            "id": "emp-1",
            "employee_folder_name": "MARTIN_Jean",
            "employment_status": "actif",
            "user_id": None,
        }
        row = create_employee_imported(employee_payload, company_id)
        assert row["employment_status"] == "actif"
        repo.create.assert_called_once()
        call_data = repo.create.call_args[0][0]
        assert call_data.get("user_id") is None
        assert call_data.get("employment_status") == "actif"
        assert call_data.get("username") == "jean.martin"
        mock_store_pdf.assert_called_once()
        assert mock_store_pdf.call_args.args == ("emp-1", company_id)
        assert mock_store_pdf.call_args.kwargs["username"] == "jean.martin"
