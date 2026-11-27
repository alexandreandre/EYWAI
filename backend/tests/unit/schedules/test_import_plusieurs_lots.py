"""Plusieurs relevés importés ensemble : chaque fichier a son lot (27/11).

L'écran fusionne les relevés et enregistre par le lot du dernier fichier. Le
serveur reçoit aussi les lots des autres fichiers : il reprend les notes de
chaque jour (badges, heures en plus) depuis le lot d'où vient le jour,
accepte un salarié présent seulement dans un fichier antérieur, et valide
tous les lots pour que le refus « déjà importé » les reconnaisse.
"""

from unittest.mock import patch

import pytest

from app.modules.schedules.application.exceptions import ScheduleAppError
from app.modules.schedules.schemas.ai import (
    AiCalendarProposalResponse,
    AiDayEntry,
    AiEmployeeProposal,
)
from app.modules.schedules.schemas.persist import PersistTimesheetEmployee, PersistTimesheetRequest
from app.modules.schedules.schemas.timesheet_import import TimesheetImportCommitRequest

SERVICE = "app.modules.schedules.application.timesheet_import.commit_service"


def _lot(batch_id, mois, employes, *, file_hash=None, statut="previewed"):
    return {
        "id": batch_id,
        "company_id": "c1",
        "status": statut,
        "file_hash": file_hash or f"empreinte-{batch_id}",
        "filename": f"{batch_id}.xlsx",
        "preview_json": AiCalendarProposalResponse(
            year=2026, month=mois, source="test", employees=employes,
        ).model_dump(mode="json"),
        "summary_json": {},
    }


def _salarie(eid, nom, jours, warnings=()):
    return AiEmployeeProposal(
        raw_name=nom.upper(), matched_name=nom, employee_id=eid, review_status="ok",
        match_confidence="high", days=jours, warnings=list(warnings),
    )


def _lots():
    septembre = _lot("lot-s39", 9, [
        _salarie("e1", "Salarié Un", [
            AiDayEntry(jour=21, heures=7.25, punch_entry_raw="733", punch_exit_raw="1613",
                       heures_en_plus_a_valider=0.5, motif_heures_en_plus="daily_excess"),
        ], warnings=["Jour 21 : Entrée 07:33 : avance."]),
        # Présent seulement dans le fichier de septembre.
        _salarie("e2", "Salarié Deux", [AiDayEntry(jour=22, heures=7.0, punch_entry_raw="800")]),
    ])
    octobre = _lot("lot-s43", 10, [
        _salarie("e1", "Salarié Un", [AiDayEntry(jour=21, heures=7.0, punch_entry_raw="800")]),
    ])
    return {"lot-s39": septembre, "lot-s43": octobre}


def _relus():
    return [
        PersistTimesheetEmployee(employee_id="e1", raw_name="SALARIE UN", days=[
            AiDayEntry(jour=21, heures=7.25, year=2026, month=9),
            AiDayEntry(jour=21, heures=7.0),
        ]),
        PersistTimesheetEmployee(employee_id="e2", raw_name="SALARIE DEUX", days=[
            AiDayEntry(jour=22, heures=7.0, year=2026, month=9),
        ]),
    ]


def _ecritures(mock_repo):
    return {args[0]: args[1] for args, _ in mock_repo.update_batch.call_args_list}


@patch(f"{SERVICE}.timesheet_import_repository")
def test_les_notes_de_chaque_jour_viennent_de_son_lot(mock_repo):
    from app.modules.schedules.application.timesheet_import.commit_service import (
        appliquer_revue_au_lot,
    )

    lots = _lots()
    mock_repo.get_batch.side_effect = lambda bid, **_: lots.get(bid)

    appliquer_revue_au_lot("lot-s43", company_id="c1", employees=_relus(), autres_lots=["lot-s39"])

    principal = _ecritures(mock_repo)["lot-s43"]
    un = next(e for e in principal["preview_json"]["employees"] if e["employee_id"] == "e1")
    jours = {(d["month"], d["jour"]): d for d in un["days"]}
    assert jours[(9, 21)]["punch_entry_raw"] == "733"
    assert jours[(9, 21)]["heures_en_plus_a_valider"] == 0.5
    assert jours[(None, 21)]["punch_entry_raw"] == "800"
    assert "Jour 21 : Entrée 07:33 : avance." in un["warnings"] or any(
        "07:33" in w for w in un["warnings"]
    )
    assert principal["summary_json"]["lots_fusionnes"] == ["lot-s39"]


@patch(f"{SERVICE}.timesheet_import_repository")
def test_un_salarie_d_un_fichier_anterieur_est_accepte(mock_repo):
    from app.modules.schedules.application.timesheet_import.commit_service import (
        appliquer_revue_au_lot,
    )

    lots = _lots()
    mock_repo.get_batch.side_effect = lambda bid, **_: lots.get(bid)

    appliquer_revue_au_lot("lot-s43", company_id="c1", employees=_relus(), autres_lots=["lot-s39"])

    principal = _ecritures(mock_repo)["lot-s43"]
    deux = next(e for e in principal["preview_json"]["employees"] if e["employee_id"] == "e2")
    assert [(d["jour"], d["month"], d["punch_entry_raw"]) for d in deux["days"]] == [(22, 9, "800")]


@patch(f"{SERVICE}.timesheet_import_repository")
def test_chaque_lot_garde_les_jours_relus_de_son_fichier(mock_repo):
    """Le refus « déjà importé » et la relecture lisent ce qu'a écrit chaque lot."""
    from app.modules.schedules.application.timesheet_import.commit_service import (
        appliquer_revue_au_lot,
    )

    lots = _lots()
    mock_repo.get_batch.side_effect = lambda bid, **_: lots.get(bid)

    appliquer_revue_au_lot("lot-s43", company_id="c1", employees=_relus(), autres_lots=["lot-s39"])

    s39 = _ecritures(mock_repo)["lot-s39"]["preview_json"]["employees"]
    par_salarie = {e["employee_id"]: [(d["jour"], d["month"], d["heures"]) for d in e["days"]] for e in s39}
    assert par_salarie == {"e1": [(21, None, 7.25)], "e2": [(22, None, 7.0)]}


@patch(f"{SERVICE}.timesheet_import_repository")
def test_un_salarie_absent_de_tous_les_lots_est_nomme(mock_repo):
    from app.modules.schedules.application.timesheet_import.commit_service import (
        appliquer_revue_au_lot,
    )

    lots = _lots()
    mock_repo.get_batch.side_effect = lambda bid, **_: lots.get(bid)
    relus = [PersistTimesheetEmployee(
        employee_id="0b7c-uuid", raw_name="Jeanne Exemple",
        days=[AiDayEntry(jour=21, heures=7.0)],
    )]

    with pytest.raises(ScheduleAppError) as err:
        appliquer_revue_au_lot("lot-s43", company_id="c1", employees=relus, autres_lots=["lot-s39"])
    assert "Jeanne Exemple" in str(err.value)
    assert "0b7c-uuid" not in str(err.value)


@patch(f"{SERVICE}.timesheet_import_repository")
def test_l_appel_a_un_seul_lot_reste_compatible(mock_repo):
    from app.modules.schedules.application.timesheet_import.commit_service import (
        appliquer_revue_au_lot,
    )

    lots = _lots()
    mock_repo.get_batch.side_effect = lambda bid, **_: lots.get(bid)
    appliquer_revue_au_lot("lot-s43", company_id="c1", employees=[
        PersistTimesheetEmployee(employee_id="e1", days=[AiDayEntry(jour=21, heures=6.5)]),
    ])

    ecrits = _ecritures(mock_repo)
    assert list(ecrits) == ["lot-s43"]
    assert "lots_fusionnes" not in ecrits["lot-s43"].get("summary_json", {})


@patch(f"{SERVICE}.record_schedule_import_run")
@patch(f"{SERVICE}.schedule_repository")
@patch(f"{SERVICE}.timesheet_import_repository")
@patch(f"{SERVICE}.get_employee_company_and_statut")
def test_le_commit_valide_aussi_les_lots_fusionnes(mock_statut, mock_repo, mock_sched, _audit):
    from app.modules.schedules.application.timesheet_import.commit_service import (
        commit_batch_bulk,
    )

    lots = _lots()
    lots["lot-s43"]["summary_json"] = {"lots_fusionnes": ["lot-s39"]}
    mock_repo.get_batch.side_effect = lambda bid, **_: lots.get(bid)
    mock_statut.return_value = ("c1", "CDI")
    mock_sched.list_schedules_for_employees.return_value = {}

    commit_batch_bulk("lot-s43", company_id="c1", request=TimesheetImportCommitRequest())

    ecrits = _ecritures(mock_repo)
    assert ecrits["lot-s43"]["status"] == "committed"
    assert ecrits["lot-s39"]["status"] == "committed"
    assert ecrits["lot-s39"]["summary_json"]["fusionne_dans"] == "lot-s43"
    mock_repo.release_committed_file_hash_lock.assert_any_call(
        "c1", "empreinte-lot-s39", keep_batch_id="lot-s39"
    )


def test_la_requete_porte_les_lots_de_tous_les_fichiers():
    req = PersistTimesheetRequest(year=2026, month=10, batch_id="lot-s43",
                                  batch_ids=["lot-s39", "lot-s43"])
    assert req.batch_ids == ["lot-s39", "lot-s43"]
    assert PersistTimesheetRequest(year=2026, month=10).batch_ids == []
