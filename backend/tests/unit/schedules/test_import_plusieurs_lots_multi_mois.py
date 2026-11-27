"""Garde par fichier sur le chemin des lots à plusieurs mois (27/11).

Deux relevés à cheval sur septembre et octobre, importés ensemble : X refait
(son premier import a écrit 7 h le 29/09 et le 01/10, corrigés depuis à la
main) et Y nouveau (le 02/10 porte déjà 7 h au calendrier). Chaque jour
est jugé par la garde de son fichier, dans les deux ordres.
"""

from unittest.mock import patch

import pytest

from app.modules.schedules.schemas.ai import (
    AiCalendarProposalResponse,
    AiDayEntry,
    AiEmployeeProposal,
)
from app.modules.schedules.schemas.persist import PersistTimesheetEmployee
from app.modules.schedules.schemas.timesheet_import import TimesheetImportCommitRequest

SERVICE = "app.modules.schedules.application.timesheet_import.commit_service"
REIMPORT = "app.modules.schedules.application.timesheet_import.reimport_service"


def _ligne(jours):
    return AiEmployeeProposal(
        raw_name="SALARIE UN", matched_name="Salarié Un", employee_id="e1",
        review_status="ok", match_confidence="high", days=jours,
    )


def _lot_multi_mois(batch_id, ancre, groupes, summary=None):
    annee, mois = ancre
    return {
        "id": batch_id, "company_id": "c1", "status": "previewed", "user_id": "u1",
        "file_hash": f"h-{batch_id}", "filename": f"{batch_id}.xlsx",
        "preview_json": AiCalendarProposalResponse(
            year=annee, month=mois, source="test",
            employees=[_ligne(groupes[mois])],
        ).model_dump(mode="json"),
        "summary_json": {
            "multi_month": True,
            "month_groups": [
                {"year": 2026, "month": m, "employees": [{
                    "employee_id": "e1", "raw_name": "SALARIE UN", "review_status": "ok",
                    "days": [d.model_dump(mode="json") for d in jours],
                }]}
                for m, jours in sorted(groupes.items())
            ],
            **(summary or {}),
        },
    }


def _lots():
    x = _lot_multi_mois(
        "x-refait", (2026, 9),
        {9: [AiDayEntry(jour=29, heures=7.0)], 10: [AiDayEntry(jour=1, heures=7.0)]},
        summary={
            "reimport": True, "previous_committed_batch_id": "x-ancien",
            "reimport_fichiers": [{"filename": "x.xlsx", "file_hash": "h-x-refait",
                                   "previous_committed_batch_id": "x-ancien"}],
        },
    )
    y = _lot_multi_mois(
        "y-nouveau", (2026, 10),
        {9: [AiDayEntry(jour=30, heures=7.0)], 10: [AiDayEntry(jour=2, heures=6.75)]},
    )
    # Premier import de X, lui aussi sur deux mois : 7 h le 29/09 et le 01/10.
    ancien = _lot_multi_mois(
        "x-ancien", (2026, 9),
        {9: [AiDayEntry(jour=29, heures=7.0)], 10: [AiDayEntry(jour=1, heures=7.0)]},
    )
    ancien.update(status="committed", completed_at="2026-11-20T10:00:00")
    return {"x-refait": x, "y-nouveau": y, "x-ancien": ancien}


def _calendrier(ids, annee, mois):
    jours = {9: [{"jour": 29, "heures_faites": 6.0, "type": "travail"}],
             10: [{"jour": 1, "heures_faites": 5.0, "type": "travail"},
                  {"jour": 2, "heures_faites": 7.0, "type": "travail"}]}[mois]
    return {"e1": {"employee_id": "e1", "year": annee, "month": mois,
                   "actual_hours": {"calendrier_reel": jours}}}


@pytest.mark.parametrize("principal", ["x-refait", "y-nouveau"])
def test_garde_par_fichier_sur_les_lots_a_plusieurs_mois(principal):
    from app.modules.schedules.application.timesheet_import.commit_service import (
        appliquer_revue_au_lot,
        commit_batch_bulk,
    )

    lots = _lots()
    autre = "y-nouveau" if principal == "x-refait" else "x-refait"
    relus = [PersistTimesheetEmployee(employee_id="e1", raw_name="SALARIE UN", days=[
        AiDayEntry(jour=29, heures=7.0, year=2026, month=9),
        AiDayEntry(jour=30, heures=7.0, year=2026, month=9),
        AiDayEntry(jour=1, heures=7.0, year=2026, month=10),
        AiDayEntry(jour=2, heures=6.75, year=2026, month=10),
    ])]

    def update_batch(bid, modifs):
        lots[bid] = {**lots[bid], **modifs}

    with patch(f"{SERVICE}.timesheet_import_repository") as repo, \
         patch(f"{REIMPORT}.timesheet_import_repository") as repo_reimport, \
         patch(f"{SERVICE}.schedule_repository") as sched, \
         patch(f"{SERVICE}.admin_repo") as admin, \
         patch(f"{SERVICE}.get_employee_company_and_statut", return_value=("c1", "CDI")), \
         patch(f"{SERVICE}.record_schedule_import_run"):
        repo.get_batch.side_effect = lambda bid, **_: lots.get(bid)
        repo.update_batch.side_effect = update_batch
        repo.is_cancel_requested.return_value = False
        repo_reimport.get_batch.side_effect = lambda bid, **_: lots.get(bid)
        admin.list_company_employees.return_value = [{"id": "e1", "company_id": "c1", "statut": "CDI"}]
        sched.list_schedules_for_employees.side_effect = _calendrier
        appliquer_revue_au_lot(principal, company_id="c1", employees=relus, autres_lots=[autre])
        resultat = commit_batch_bulk(principal, company_id="c1", request=TimesheetImportCommitRequest())
        ecrits = {}
        for (payloads,), _ in sched.bulk_upsert_schedules.call_args_list:
            for p in payloads:
                for j in (p.get("actual_hours") or {}).get("calendrier_reel") or []:
                    ecrits[(p["month"], j["jour"])] = j.get("heures_faites")

    gardees = {(c["mois"], c["jour"]) for c in resultat.get("corrections_gardees") or []}
    # Les deux corrections de X, y compris celle du mois hors de son ancre.
    assert gardees == {(9, 29), (10, 1)}
    assert ecrits.get((10, 1)) != 7.0
    assert ecrits.get((9, 29)) != 7.0
    assert ecrits[(9, 30)] == 7.0
    assert ecrits[(10, 2)] == 6.75
    assert lots[autre]["status"] == "committed"
