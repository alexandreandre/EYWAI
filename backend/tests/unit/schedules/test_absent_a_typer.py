"""Case « absent » de l'import de pointages (retour d'Elsa du 28/10/2026).

Un jour vide coché « absent » à l'import devient, au planning prévu, un jour
« absent, type à donner » : il ne retire rien du salaire par lui-même, il
bloque la génération sans forçage possible tant que la RH ne lui a pas donné
son type (congé, RTT, arrêt ou absence non payée).
"""

from __future__ import annotations

from datetime import date
from unittest.mock import patch

import pytest

from app.modules.schedules.application.persist_timesheet import _merge_days
from app.modules.schedules.domain.absent_a_typer import (
    TYPE_ABSENT_A_TYPER,
    message_absents_a_typer,
)
from app.modules.schedules.domain.periode_a_saisir import periode_a_saisir
from app.modules.schedules.schemas.persist import PersistTimesheetEmployee

pytestmark = pytest.mark.unit

FENETRE = (date(2026, 9, 1), date(2026, 9, 30))


def _septembre(absents: tuple[int, ...] = ()):
    prevu, reel = [], []
    for jour in range(1, 31):
        if date(2026, 9, jour).weekday() >= 5:
            prevu.append({"jour": jour, "type": "weekend", "heures_prevues": 0.0})
            continue
        if jour in absents:
            prevu.append({"jour": jour, "type": TYPE_ABSENT_A_TYPER, "heures_prevues": 7.0})
            reel.append({"jour": jour, "type": TYPE_ABSENT_A_TYPER, "heures_faites": None})
            continue
        prevu.append({"jour": jour, "type": "travail", "heures_prevues": 7.0})
        reel.append({"jour": jour, "type": "travail", "heures_faites": 7.0})
    return {(2026, 9): (prevu, reel)}


class TestPeriodeASaisir:
    def test_un_jour_absent_sans_type_est_releve_a_part(self):
        periode = periode_a_saisir(
            annee=2026, mois=9, fenetre=FENETRE, calendriers=_septembre((9, 10))
        )
        assert periode.absents_a_typer == (date(2026, 9, 9), date(2026, 9, 10))

    def test_il_n_est_pas_un_jour_a_saisir(self):
        periode = periode_a_saisir(
            annee=2026, mois=9, fenetre=FENETRE, calendriers=_septembre((9,))
        )
        assert periode.manquants == ()
        assert periode.statut == "saisi"

    def test_hors_contrat_il_n_est_pas_releve(self):
        periode = periode_a_saisir(
            annee=2026, mois=9, fenetre=FENETRE, calendriers=_septembre((9,)),
            date_entree=date(2026, 9, 14),
        )
        assert periode.absents_a_typer == ()


class TestMessage:
    def test_le_refus_nomme_la_personne_les_jours_et_la_sortie(self):
        assert message_absents_a_typer("Octavie", [date(2026, 9, 9), date(2026, 9, 10)]) == (
            "Octavie a des jours marqués « absent » sans type : les 9 et 10 septembre. "
            "Donnez le type de chaque jour dans le calendrier (congé, RTT, arrêt "
            "ou absence non payée) : la paie reste bloquée jusque-là."
        )

    def test_un_seul_jour(self):
        assert message_absents_a_typer("Octavie", [date(2026, 9, 9)]).startswith(
            "Octavie a un jour marqué « absent » sans type : le 9 septembre."
        )


class TestEnregistrementDeLImport:
    def test_la_marque_change_le_type_prevu_sans_toucher_aux_heures(self):
        stocke = [{"jour": 9, "type": "travail", "heures_prevues": 7.0}]
        jour = PersistTimesheetEmployee.model_validate(
            {"employee_id": "e1", "days": [{"jour": 9, "heures": None, "type": TYPE_ABSENT_A_TYPER, "nature": "prevu"}]}
        ).days
        fusion = _merge_days(stocke, jour, "prevu", warnings=[])
        assert fusion == [{"jour": 9, "type": TYPE_ABSENT_A_TYPER, "heures_prevues": 7.0}]

    def test_une_absence_validee_n_est_pas_remplacee_par_la_marque(self):
        stocke = [{"jour": 9, "type": "conges_payes", "heures_prevues": 0.0, "origine": "absence"}]
        jour = PersistTimesheetEmployee.model_validate(
            {"employee_id": "e1", "days": [{"jour": 9, "heures": None, "type": TYPE_ABSENT_A_TYPER, "nature": "prevu"}]}
        ).days
        avertissements: list = []
        fusion = _merge_days(stocke, jour, "prevu", warnings=avertissements)
        assert fusion[0]["type"] == "conges_payes"
        assert avertissements and avertissements[0]["code"] == "absence_validee_preservee"


@patch("app.modules.schedules.application.timesheet_import.commit_service.get_employee_company_and_statut")
def test_premier_import_du_mois_le_planning_par_defaut_est_cree_autour_de_la_marque(mock_statut):
    """Un mois sans ligne : la marque seule ne doit pas laisser le reste du
    mois sans planning (tous les jours ouvrés « à saisir »)."""
    from app.modules.schedules.application.timesheet_import.commit_service import (
        _upsert_employees_for_month,
    )

    mock_statut.return_value = ("c1", "CDI")
    emp = PersistTimesheetEmployee.model_validate({
        "employee_id": "e1",
        "days": [
            {"jour": 8, "heures": 7.0, "type": "travail", "nature": "reel"},
            {"jour": 9, "heures": None, "type": TYPE_ABSENT_A_TYPER, "nature": "prevu"},
            {"jour": 9, "heures": None, "type": TYPE_ABSENT_A_TYPER, "nature": "reel"},
        ],
    })
    payloads, *_ = _upsert_employees_for_month(
        company_id="c1", year=2026, month=9, employees=[emp], existing_rows={},
    )
    prevu = {e["jour"]: e for e in payloads[0]["planned_calendar"]["calendrier_prevu"]}
    assert len(prevu) == 30
    assert prevu[9]["type"] == TYPE_ABSENT_A_TYPER
    assert prevu[8]["type"] == "travail"
    assert prevu[12]["type"] == "weekend"


@patch("app.modules.schedules.application.timesheet_import.commit_service.get_employee_company_and_statut")
def test_un_jour_coche_absent_compte_pour_un_jour_ecrit(mock_statut):
    """Le jour coché part au prévu et au réel : le message « N jours mis à jour »
    ne doit le compter qu'une fois."""
    from app.modules.schedules.application.timesheet_import.commit_service import (
        _upsert_employees_for_month,
    )

    mock_statut.return_value = ("c1", "CDI")
    emp = PersistTimesheetEmployee.model_validate({
        "employee_id": "e1",
        "days": [
            {"jour": 8, "heures": 7.0, "type": "travail", "nature": "reel"},
            {"jour": 9, "heures": None, "type": TYPE_ABSENT_A_TYPER, "nature": "prevu"},
            {"jour": 9, "heures": None, "type": TYPE_ABSENT_A_TYPER, "nature": "reel"},
        ],
    })
    _, total, *_ = _upsert_employees_for_month(
        company_id="c1", year=2026, month=9, employees=[emp], existing_rows={},
    )
    assert total == 2
