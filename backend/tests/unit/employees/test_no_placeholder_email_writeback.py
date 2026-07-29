"""Une adresse technique de compte Auth ne doit jamais devenir l'adresse de contact.

Supabase Auth exige une adresse pour créer un compte. Quand le salarié n'en a pas, on en
fabrique une pour Auth — mais elle reste un identifiant interne. La recopier dans
`employees.email` transforme un identifiant technique en adresse de contact et fait croire
que le salarié est joignable.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.modules.employees.application.account_provisioning import (
    provision_collaborator_account,
)
from app.modules.employees.domain.rules import is_dsn_import_placeholder_email

pytestmark = pytest.mark.unit


def _provision(employee: dict) -> MagicMock:
    """Provisionne un compte et rend le mock du dépôt salarié pour inspection."""
    with (
        patch(
            "app.modules.employees.application.account_provisioning.allocate_collaborator_username",
            return_value="sans.mail",
        ),
        patch("app.modules.employees.application.commands._grant_collaborator_company_access"),
        patch(
            "app.modules.employees.application.account_provisioning.generate_credentials_pdf",
            return_value=b"%PDF-1.4",
        ),
        patch(
            "app.modules.employees.application.account_provisioning.get_auth_provider"
        ) as auth_provider,
        patch(
            "app.modules.employees.application.account_provisioning.get_company_reader"
        ) as company_reader,
        patch(
            "app.modules.employees.application.account_provisioning.get_storage_provider"
        ) as storage_provider,
        patch("app.modules.employees.application.account_provisioning._profile_repository"),
        patch(
            "app.modules.employees.application.account_provisioning._employee_repository"
        ) as repo,
    ):
        repo.get_by_id.return_value = employee
        repo.update.return_value = {}
        auth = MagicMock()
        auth.create_user.return_value = "user-new"
        auth_provider.return_value = auth
        company_reader.return_value.get_company_data.return_value = {"company_name": "Test SA"}
        storage = MagicMock()
        storage.list_files.return_value = []
        storage_provider.return_value = storage

        provision_collaborator_account("emp-1", "company-1", "rh-1")
        return repo


BASE_EMPLOYEE = {
    "id": "emp-1",
    "company_id": "company-1",
    "first_name": "Sans",
    "last_name": "Mail",
    "job_title": "Opérateur",
    "username": "sans.mail",
    "employee_folder_name": "MAIL_Sans",
}


def test_adresse_technique_non_recopiee_dans_la_fiche() -> None:
    repo = _provision({**BASE_EMPLOYEE, "email": None})

    repo.update.assert_called_once()
    patch_ = repo.update.call_args[0][1]
    assert "email" not in patch_, (
        "L'adresse technique du compte Auth ne doit pas atterrir dans employees.email, "
        f"or la fiche reçoit {patch_.get('email')!r}"
    )
    assert patch_["user_id"] == "user-new"
    assert patch_["username"] == "sans.mail"


def test_adresse_reelle_conservee_dans_la_fiche() -> None:
    """Une vraie adresse doit continuer d'être enregistrée normalement."""
    repo = _provision({**BASE_EMPLOYEE, "email": "sans.mail@exemple.fr"})

    patch_ = repo.update.call_args[0][1]
    assert patch_["email"] == "sans.mail@exemple.fr"
    assert not is_dsn_import_placeholder_email(patch_["email"])


def test_le_compte_auth_est_bien_cree_sans_adresse_reelle() -> None:
    """Absence d'adresse ne doit pas empêcher la création du compte."""
    repo = _provision({**BASE_EMPLOYEE, "email": None})

    assert repo.update.call_args[0][1]["user_id"] == "user-new"
