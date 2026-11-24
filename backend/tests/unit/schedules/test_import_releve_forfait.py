"""Import de relevés : un salarié au forfait jours reçoit des jours, pas des heures (24/11).

L'import écrivait `heures_faites` (et `heures_prevues`) en heures pour tout le
monde. Au forfait, le moteur lit 1 = jour prévu / travaillé : un réel à 7 h face
à un prévu à 1 devenait une absence injustifiée retenue sur le salaire. L'écran
(`update_actual_hours`) ramène déjà à 1/0 ; l'import fait de même, sur les jours
importés seulement. Un 0 reste 0, un jour sans valeur reste sans valeur.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from app.modules.schedules.application.timesheet_import.commit_service import (
    _upsert_employees_for_month,
    _upsert_employees_for_month_fast,
)
from app.modules.schedules.schemas.persist import PersistTimesheetEmployee

pytestmark = pytest.mark.unit

_STATUT = "app.modules.schedules.application.timesheet_import.commit_service.get_employee_company_and_statut"


def _salarie():
    return PersistTimesheetEmployee.model_validate({
        "employee_id": "e1",
        "days": [
            {"jour": 2, "heures": 7.0, "type": "travail", "nature": "reel"},
            {"jour": 3, "heures": 0.0, "type": "travail", "nature": "reel"},
            {"jour": 4, "heures": 7.8, "type": "travail", "nature": "prevu"},
        ],
    })


def _existant():
    return {"e1": {
        "planned_calendar": {"calendrier_prevu": [
            {"jour": 5, "type": "travail", "heures_prevues": 7.8},
        ]},
        "actual_hours": {"calendrier_reel": [{"jour": 5, "type": "travail", "heures_faites": None}]},
    }}


def _jours(payload):
    reel = {e["jour"]: e.get("heures_faites") for e in payload["actual_hours"]["calendrier_reel"]}
    prevu = {e["jour"]: e.get("heures_prevues") for e in payload["planned_calendar"]["calendrier_prevu"]}
    return reel, prevu


@patch(_STATUT, return_value=("c1", "Cadre au forfait jour"))
def test_import_au_forfait_ecrit_des_jours(_statut):
    payloads, *_ = _upsert_employees_for_month(
        company_id="c1", year=2026, month=11, employees=[_salarie()], existing_rows=_existant(),
    )
    reel, prevu = _jours(payloads[0])
    assert reel[2] == 1
    assert reel[3] == 0
    assert prevu[4] == 1
    # Les jours non importés ne sont pas touchés.
    assert reel[5] is None
    assert prevu[5] == 7.8


@patch(_STATUT, return_value=("c1", "Cadre"))
def test_import_en_heures_garde_les_heures(_statut):
    payloads, *_ = _upsert_employees_for_month(
        company_id="c1", year=2026, month=11, employees=[_salarie()], existing_rows=_existant(),
    )
    reel, prevu = _jours(payloads[0])
    assert reel[2] == 7.0
    assert prevu[4] == 7.8


@pytest.mark.parametrize(("au_forfait", "attendu_reel", "attendu_prevu"), [({"e1"}, 1, 1), (set(), 7.0, 7.8)])
def test_import_rapide_lit_le_forfait(au_forfait, attendu_reel, attendu_prevu):
    payloads, *_ = _upsert_employees_for_month_fast(
        company_id="c1", year=2026, month=11, employees=[_salarie()], existing_rows=_existant(),
        employee_company_ids={"e1": "c1"}, au_forfait=au_forfait,
    )
    reel, prevu = _jours(payloads[0])
    assert reel[2] == attendu_reel
    assert reel[3] == 0
    assert prevu[4] == attendu_prevu


def test_lot_multi_mois_lit_la_case_dans_la_fiche():
    """Le lot sur plusieurs mois prend le forfait sur la fiche (case cochée)."""
    from unittest.mock import patch as _patch

    from app.modules.schedules.schemas.ai import AiCalendarProposalResponse
    from app.modules.schedules.schemas.timesheet_import import TimesheetImportCommitRequest

    service = "app.modules.schedules.application.timesheet_import.commit_service"
    lot = {
        "id": "b-1", "company_id": "c1", "status": "previewed", "file_hash": "h-1",
        "preview_json": AiCalendarProposalResponse(
            year=2026, month=11, source="test", employees=[]
        ).model_dump(mode="json"),
        "summary_json": {
            "multi_month": True,
            "month_groups": [{
                "year": 2026, "month": 11,
                "employees": [{"employee_id": "e1", "raw_name": "X", "days": [
                    {"jour": 2, "heures": 7.0, "type": "travail", "nature": "reel"},
                ]}],
            }],
        },
    }
    with _patch(f"{service}.record_schedule_import_run"), \
         _patch(f"{service}.admin_repo") as admin, \
         _patch(f"{service}.schedule_repository") as sched, \
         _patch(f"{service}.timesheet_import_repository") as repo, \
         _patch(f"{service}.arrets_valides_reader"):
        repo.get_batch.return_value = lot
        repo.is_cancel_requested.return_value = False
        admin.list_company_employees.return_value = [
            {"id": "e1", "company_id": "c1", "statut": "Cadre", "is_forfait_jour": True}
        ]
        sched.list_schedules_for_employees.return_value = {}
        from app.modules.schedules.application.timesheet_import.commit_service import (
            commit_batch_bulk,
        )

        commit_batch_bulk("b-1", company_id="c1", request=TimesheetImportCommitRequest())
        (payloads,), _ = sched.bulk_upsert_schedules.call_args
    reel = {e["jour"]: e["heures_faites"] for e in payloads[0]["actual_hours"]["calendrier_reel"]}
    assert reel[2] == 1


@patch(_STATUT, return_value=("c1", "Cadre au forfait jour"))
def test_import_au_forfait_garde_les_heures_sur_un_arret(_statut):
    """Un réel importé sur un jour prévu en arrêt garde ses heures (signalé en
    conflit) : à 1, le moteur du forfait y verrait un jour travaillé."""
    existant = _existant()
    existant["e1"]["planned_calendar"]["calendrier_prevu"].append(
        {"jour": 2, "type": "arret_maladie", "heures_prevues": 0, "origine": "absence"}
    )
    payloads, *_ = _upsert_employees_for_month(
        company_id="c1", year=2026, month=11, employees=[_salarie()], existing_rows=existant,
    )
    reel, _ = _jours(payloads[0])
    assert reel[2] == 7.0


def test_reimport_au_forfait_ne_voit_pas_de_correction_a_la_main():
    """Le lot précédent a lu 7 h, le calendrier porte 1 (écrit en jours), le
    fichier relit 7 h : rien n'a été corrigé à la main."""
    from app.modules.schedules.application.timesheet_import.reimport_service import (
        GardeDesCorrections,
    )
    from app.modules.schedules.domain.corrections_a_la_main import ValeurJour

    garde = GardeDesCorrections(ecrits={("e1", 2026, 11, 2): ValeurJour(7.0, "travail")})
    emp = PersistTimesheetEmployee.model_validate({
        "employee_id": "e1",
        "days": [{"jour": 2, "heures": 7.0, "type": "travail", "nature": "reel"}],
    })
    lignes = {"e1": {"actual_hours": {"calendrier_reel": [
        {"jour": 2, "type": "travail", "heures_faites": 1},
    ]}}}
    restants = garde.filtrer([emp], 2026, 11, lignes, au_forfait={"e1"})
    assert garde.gardees == []
    assert restants and restants[0].days
    # Sans la case, la même lecture voit une correction (comportement en heures).
    garde_heures = GardeDesCorrections(ecrits={("e1", 2026, 11, 2): ValeurJour(7.0, "travail")})
    garde_heures.filtrer([emp], 2026, 11, lignes)
    assert len(garde_heures.gardees) == 1
