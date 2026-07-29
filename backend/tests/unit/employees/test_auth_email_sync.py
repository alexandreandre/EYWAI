"""Quand la vraie adresse arrive, le compte de connexion doit suivre.

85 personnes ont déjà leur adresse réelle en fiche et se connectent pourtant encore avec
une adresse fabriquée : aucun code ne mettait à jour l'adresse d'un compte Auth existant.
Sans cette synchronisation, la réinitialisation de mot de passe part vers un domaine mort.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.modules.employees.application.auth_email_sync import (
    SyncOutcome,
    sync_auth_email_for_employee,
)

pytestmark = pytest.mark.unit

PLACEHOLDER = "import.vanessa.amate.383122@534386495.dsn-import.local"
REELLE = "amatevanessa@yahoo.fr"


def _auth(current_email: str | None):
    auth = MagicMock()
    auth.get_user_email.return_value = current_email
    return auth


def test_login_fabrique_realigne_sur_l_adresse_reelle() -> None:
    auth = _auth(PLACEHOLDER)

    outcome = sync_auth_email_for_employee(
        {"id": "emp-1", "user_id": "user-1", "email": REELLE}, auth=auth
    )

    auth.update_user_email.assert_called_once_with("user-1", REELLE)
    assert outcome is SyncOutcome.REALIGNED


def test_login_deja_reel_jamais_ecrase() -> None:
    """Une adresse de connexion choisie par la personne ne doit pas être écrasée."""
    auth = _auth("vamate@maji-invest.fr")

    outcome = sync_auth_email_for_employee(
        {"id": "emp-1", "user_id": "user-1", "email": REELLE}, auth=auth
    )

    auth.update_user_email.assert_not_called()
    assert outcome is SyncOutcome.SKIPPED_REAL_LOGIN


def test_adresse_de_fiche_fabriquee_ne_declenche_rien() -> None:
    auth = _auth(PLACEHOLDER)

    outcome = sync_auth_email_for_employee(
        {"id": "emp-1", "user_id": "user-1", "email": PLACEHOLDER}, auth=auth
    )

    auth.update_user_email.assert_not_called()
    assert outcome is SyncOutcome.SKIPPED_NO_REAL_EMAIL


def test_salarie_sans_compte_ne_declenche_rien() -> None:
    auth = _auth(None)

    outcome = sync_auth_email_for_employee(
        {"id": "emp-1", "user_id": None, "email": REELLE}, auth=auth
    )

    auth.update_user_email.assert_not_called()
    assert outcome is SyncOutcome.SKIPPED_NO_ACCOUNT


def test_adresse_deja_prise_ne_leve_pas_d_exception() -> None:
    """Corriger une adresse de contact ne doit jamais faire échouer l'enregistrement."""
    auth = _auth(PLACEHOLDER)
    auth.update_user_email.side_effect = RuntimeError("email already registered")

    with patch(
        "app.modules.employees.application.auth_email_sync.logger"
    ) as journal:
        outcome = sync_auth_email_for_employee(
            {"id": "emp-1", "user_id": "user-1", "email": REELLE}, auth=auth
        )

    assert outcome is SyncOutcome.FAILED
    journal.warning.assert_called_once()
    assert "emp-1" in " ".join(str(a) for a in journal.warning.call_args[0])


def test_meme_adresse_des_deux_cotes_est_un_no_op() -> None:
    auth = _auth(REELLE)

    outcome = sync_auth_email_for_employee(
        {"id": "emp-1", "user_id": "user-1", "email": REELLE.upper()}, auth=auth
    )

    auth.update_user_email.assert_not_called()
    assert outcome is SyncOutcome.SKIPPED_REAL_LOGIN


class TestBranchementSurUpdateEmployee:
    """La synchronisation doit partir du point de passage unique des mises à jour."""

    def test_update_employee_declenche_la_synchronisation(self) -> None:
        from app.modules.employees.application import commands

        with (
            patch.object(commands, "_employee_repository") as repo,
            patch.object(commands, "sync_auth_email_for_employee") as sync,
            patch.object(commands, "_maybe_activate_after_onboarding"),
            patch.object(commands, "enrich_employee_profile_completeness", side_effect=lambda x: x),
        ):
            repo.update.return_value = {"id": "emp-1"}
            repo.get_by_id_only.return_value = {
                "id": "emp-1",
                "user_id": "user-1",
                "email": REELLE,
            }

            commands.update_employee("emp-1", {"email": REELLE})

        sync.assert_called_once()
        assert sync.call_args[0][0]["email"] == REELLE

    def test_update_sans_email_ne_touche_pas_au_compte(self) -> None:
        from app.modules.employees.application import commands

        with (
            patch.object(commands, "_employee_repository") as repo,
            patch.object(commands, "sync_auth_email_for_employee") as sync,
            patch.object(commands, "_maybe_activate_after_onboarding"),
            patch.object(commands, "enrich_employee_profile_completeness", side_effect=lambda x: x),
        ):
            repo.update.return_value = {"id": "emp-1"}
            repo.get_by_id_only.return_value = {"id": "emp-1"}

            commands.update_employee("emp-1", {"job_title": "Chef d'équipe"})

        sync.assert_not_called()
