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
        patch.object(commands, "periodes_deposees", return_value=frozenset()) as deposee,
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


def test_un_code_hors_liste_choisi_par_la_rh_est_refuse():
    import pytest
    from fastapi import HTTPException

    with _fiche({"pcs": "9999"}) as (repo, _):
        with pytest.raises(HTTPException) as refus:
            commands.update_employee("emp-1", {"classification_conventionnelle": {"pcs": "999a"}})
    assert refus.value.status_code == 400
    assert "999a" in refus.value.detail and "liste officielle" in refus.value.detail
    repo.update.assert_not_called()


def test_un_code_hors_liste_deja_sur_la_fiche_ne_bloque_pas_une_autre_modification():
    with _fiche({"pcs": "311a"}) as (repo, _):
        commands.update_employee("emp-1", {"classification_conventionnelle": {"pcs": "311a", "idcc": "0292"}})
    assert _ecrit(repo)["pcs"] == "311a"


def test_creation_avec_un_code_hors_liste_refusee_avant_tout():
    import asyncio

    import pytest
    from fastapi import HTTPException

    with patch.object(commands, "get_auth_provider") as auth:
        with pytest.raises(HTTPException) as refus:
            asyncio.run(
                commands.create_employee(
                    {"first_name": "Ana", "last_name": "Fictive", "classification_conventionnelle": {"pcs": "999a"}},
                    "soc-1",
                )
            )
    assert refus.value.status_code == 400 and "999a" in refus.value.detail
    auth.assert_not_called()
