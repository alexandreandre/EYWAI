"""Le changement de code PCS-ESE part du point de passage unique des mises à jour de fiche."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import date
from unittest.mock import patch

from app.modules.employees.application import commands


@contextmanager
def _fiche(classification):
    with (
        patch.object(commands, "_employee_repository") as repo,
        patch.object(commands, "sync_auth_email_for_employee"),
        patch.object(commands, "_maybe_activate_after_onboarding"),
        patch.object(commands, "enrich_employee_profile_completeness", side_effect=lambda x: x),
        patch.object(commands, "derniere_periode_deposee", return_value=None) as deposee,
        patch.object(commands, "_aujourd_hui", return_value=date(2026, 11, 6)),
    ):
        repo.get_by_id_only.return_value = {
            "id": "emp-1",
            "company_id": "soc-1",
            "classification_conventionnelle": classification,
        }
        repo.update.return_value = {"id": "emp-1"}
        yield repo, deposee


def _ecrit(repo):
    return repo.update.call_args[0][1]["classification_conventionnelle"]


def test_la_rh_change_9999_l_ancien_code_est_note():
    with _fiche({"pcs": "9999", "idcc": "0292"}) as (repo, deposee):
        commands.update_employee("emp-1", {"classification_conventionnelle": {"pcs": "674a", "idcc": "0292"}})
    assert _ecrit(repo)["pcs_changement"] == {"ancien": "9999", "date": "2026-11-06"}
    deposee.assert_called_once_with("soc-1")


def test_l_import_ne_remet_pas_9999():
    with _fiche({"pcs": "674a"}) as (repo, _):
        commands.update_employee(
            "emp-1", {"classification_conventionnelle": {"pcs": "9999"}}, depuis_import=True
        )
    assert _ecrit(repo) == {"pcs": "674a"}


def test_sans_classification_rien_n_est_lu():
    with _fiche({"pcs": "9999"}) as (repo, deposee):
        commands.update_employee("emp-1", {"job_title": "Soudeur"})
    assert "classification_conventionnelle" not in repo.update.call_args[0][1]
    deposee.assert_not_called()
