"""Plusieurs relevés importés ensemble, suite de la relecture du 27/11.

- La garde des corrections faites à la main juge chaque jour avec le lot
  précédent du fichier d'où vient le jour, quel que soit l'ordre des fichiers.
- Un lot déjà validé (ou en cours) est refusé avant toute écriture.
- Un lot d'un autre utilisateur est refusé.
"""

from unittest.mock import patch

import pytest

from app.modules.schedules.application.exceptions import ScheduleAppError
from app.modules.schedules.schemas.ai import (
    AiCalendarProposalResponse,
    AiDayEntry,
    AiEmployeeProposal,
)
from app.modules.schedules.schemas.persist import PersistTimesheetEmployee
from app.modules.schedules.schemas.timesheet_import import TimesheetImportCommitRequest

SERVICE = "app.modules.schedules.application.timesheet_import.commit_service"
REIMPORT = "app.modules.schedules.application.timesheet_import.reimport_service"


def _apercu(mois, jours):
    return AiCalendarProposalResponse(
        year=2026, month=mois, source="test",
        employees=[AiEmployeeProposal(
            raw_name="SALARIE UN", matched_name="Salarié Un", employee_id="e1",
            review_status="ok", match_confidence="high", days=jours,
        )],
    ).model_dump(mode="json")


def _lots(principal: str):
    """S39 refait (lot précédent : 7 h le 21/09, corrigé à 6 h au calendrier)
    et S43 nouveau (le 21/10 porte déjà 7 h au calendrier, écrit à tort)."""
    s39 = {
        "id": "s39-refait", "company_id": "c1", "status": "previewed", "user_id": "u1",
        "file_hash": "h39", "filename": "S39.xlsx",
        "preview_json": _apercu(9, [AiDayEntry(jour=21, heures=7.0), AiDayEntry(jour=22, heures=7.0)]),
        "summary_json": {
            "reimport": True,
            "previous_committed_batch_id": "s39-ancien",
            "reimport_fichiers": [{"filename": "S39.xlsx", "file_hash": "h39",
                                   "previous_committed_batch_id": "s39-ancien"}],
        },
    }
    s43 = {
        "id": "s43", "company_id": "c1", "status": "previewed", "user_id": "u1",
        "file_hash": "h43", "filename": "S43.xlsx",
        "preview_json": _apercu(10, [AiDayEntry(jour=21, heures=6.75)]),
        "summary_json": {},
    }
    ancien = {
        "id": "s39-ancien", "company_id": "c1", "status": "committed",
        "completed_at": "2026-11-20T10:00:00",
        "preview_json": _apercu(9, [AiDayEntry(jour=21, heures=7.0), AiDayEntry(jour=22, heures=7.0)]),
        "summary_json": {},
    }
    lots = {"s39-refait": s39, "s43": s43, "s39-ancien": ancien}
    autre = "s39-refait" if principal == "s43" else "s43"
    return lots, autre


def _calendrier(ids, annee, mois):
    jours = {9: [{"jour": 21, "heures_faites": 6.0, "type": "travail"},
                 {"jour": 22, "heures_faites": 7.0, "type": "travail"}],
             10: [{"jour": 21, "heures_faites": 7.0, "type": "travail"}]}[mois]
    return {"e1": {"employee_id": "e1", "year": annee, "month": mois,
                   "actual_hours": {"calendrier_reel": jours}}}


def _relus():
    return [PersistTimesheetEmployee(employee_id="e1", raw_name="SALARIE UN", days=[
        AiDayEntry(jour=21, heures=7.0, year=2026, month=9),
        AiDayEntry(jour=22, heures=7.0, year=2026, month=9),
        AiDayEntry(jour=21, heures=6.75, year=2026, month=10),
    ])]


def _enregistrer(principal):
    from app.modules.schedules.application.timesheet_import.commit_service import (
        appliquer_revue_au_lot,
        commit_batch_bulk,
    )

    lots, autre = _lots(principal)

    def get_batch(bid, **_):
        return lots.get(bid)

    def update_batch(bid, modifs):
        lots[bid] = {**lots[bid], **modifs}

    with patch(f"{SERVICE}.timesheet_import_repository") as repo, \
         patch(f"{REIMPORT}.timesheet_import_repository") as repo_reimport, \
         patch(f"{SERVICE}.schedule_repository") as sched, \
         patch(f"{SERVICE}.get_employee_company_and_statut", return_value=("c1", "CDI")), \
         patch(f"{SERVICE}.record_schedule_import_run"):
        repo.get_batch.side_effect = get_batch
        repo.update_batch.side_effect = update_batch
        repo_reimport.get_batch.side_effect = get_batch
        sched.list_schedules_for_employees.side_effect = _calendrier
        appliquer_revue_au_lot(principal, company_id="c1", employees=_relus(), autres_lots=[autre])
        resultat = commit_batch_bulk(principal, company_id="c1", request=TimesheetImportCommitRequest())
        ecrits = {}
        for (payloads,), _ in sched.bulk_upsert_schedules.call_args_list:
            for p in payloads:
                for j in (p.get("actual_hours") or {}).get("calendrier_reel") or []:
                    ecrits[(p["month"], j["jour"])] = j.get("heures_faites")
    return resultat, ecrits


@pytest.mark.parametrize("principal", ["s43", "s39-refait"])
def test_la_garde_juge_chaque_jour_par_son_fichier_dans_les_deux_ordres(principal):
    resultat, ecrits = _enregistrer(principal)
    gardees = {(c["mois"], c["jour"]) for c in resultat.get("corrections_gardees") or []}
    # 21/09 corrigé à la main depuis le premier import de S39 : gardé (6 h reste).
    assert (9, 21) in gardees
    assert ecrits.get((9, 21)) != 7.0
    # 21/10 : S43 est un premier import, sa valeur s'écrit.
    assert (10, 21) not in gardees
    assert ecrits[(10, 21)] == 6.75


# --- Lots refusés avant toute écriture --------------------------------------


@pytest.mark.parametrize("statut", ["committed", "committing"])
@pytest.mark.parametrize("lequel", ["principal", "autre"])
def test_un_lot_deja_valide_ou_en_cours_est_refuse_avant_toute_ecriture(statut, lequel):
    from app.modules.schedules.application.timesheet_import.commit_service import (
        appliquer_revue_au_lot,
    )

    lots, autre = _lots("s43")
    lots["s43" if lequel == "principal" else autre]["status"] = statut
    with patch(f"{SERVICE}.timesheet_import_repository") as repo:
        repo.get_batch.side_effect = lambda bid, **_: lots.get(bid)
        with pytest.raises(ScheduleAppError) as err:
            appliquer_revue_au_lot("s43", company_id="c1", employees=_relus(), autres_lots=[autre])
        repo.update_batch.assert_not_called()
    assert ".xlsx" in str(err.value)


def test_un_lot_d_un_autre_utilisateur_est_refuse():
    from app.modules.schedules.application.timesheet_import.commit_service import (
        appliquer_revue_au_lot,
    )

    lots, autre = _lots("s43")
    lots[autre]["user_id"] = "u2"
    with patch(f"{SERVICE}.timesheet_import_repository") as repo:
        repo.get_batch.side_effect = lambda bid, **_: lots.get(bid)
        with pytest.raises(ScheduleAppError) as err:
            appliquer_revue_au_lot("s43", company_id="c1", employees=_relus(),
                                   autres_lots=[autre], user_id="u1")
        repo.update_batch.assert_not_called()
    assert err.value.status_code == 403
