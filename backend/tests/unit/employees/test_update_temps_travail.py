"""R-462 : un changement de temps de travail enregistré sur la fiche part vers le bloc 41 de la DSN."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import date
from unittest.mock import MagicMock, patch

from app.modules.dsn_export.domain.changement_temps_travail import CLE
from app.modules.dsn_export.domain.settings import DsnSettings
from app.modules.employees.application import commands


@contextmanager
def _fiche(**champs):
    with (
        patch.object(commands, "_employee_repository") as repo,
        patch.object(commands, "sync_auth_email_for_employee"),
        patch.object(commands, "_maybe_activate_after_onboarding"),
        patch.object(commands, "enrich_employee_profile_completeness", side_effect=lambda x: x),
        patch.object(commands, "periodes_deposees", return_value=frozenset()) as deposees,
        patch.object(commands, "_aujourd_hui", return_value=date(2026, 11, 5)),
        patch.object(
            commands.settings_repository, "charger", return_value=DsnSettings(quotite_forfait_jours="21.47")
        ) as charger,
    ):
        repo.get_by_id_only.return_value = {
            "id": "emp-1",
            "company_id": "soc-1",
            "hire_date": "2020-01-01",
            "is_forfait_jour": True,
            "is_temps_partiel": False,
            "duree_hebdomadaire": 35.0,
            "classification_conventionnelle": {"pcs": "389a"},
            **champs,
        }
        repo.update.return_value = {"id": "emp-1"}
        yield repo, charger, deposees


def _ecrit(repo):
    return repo.update.call_args[0][1]


def test_passage_a_35_h_note_les_anciennes_valeurs():
    with _fiche() as (repo, _, _d):
        commands.update_employee("emp-1", {"is_forfait_jour": False, "duree_hebdomadaire": 35.0})
    note = _ecrit(repo)["classification_conventionnelle"][CLE]
    assert note == {
        "date": "2026-11-01",
        "anciens": {"S21.G00.41.006": "20", "S21.G00.41.007": "21.47", "S21.G00.41.022": "21.47"},
    }


def test_une_fiche_sans_changement_de_temps_ne_lit_pas_le_parametrage():
    with _fiche() as (repo, charger, deposees):
        commands.update_employee("emp-1", {"job_title": "Technicienne"})
    charger.assert_not_called()
    deposees.assert_not_called()
    assert "classification_conventionnelle" not in _ecrit(repo)


def test_le_parametrage_illisible_n_empeche_pas_d_enregistrer_la_fiche():
    with _fiche() as (repo, charger, _d):
        charger.side_effect = commands.settings_repository.ParametrageDsnIllisible("x")
        commands.update_employee("emp-1", {"is_forfait_jour": False})
    assert _ecrit(repo)["is_forfait_jour"] is False


def test_l_import_dsn_ne_note_rien():
    with _fiche() as (repo, _, _d):
        commands.update_employee(
            "emp-1", {"is_forfait_jour": False}, depuis_import=True
        )
    assert CLE not in _ecrit(repo).get("classification_conventionnelle", {})
