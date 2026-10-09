"""Au réimport d'un fichier, les associations faites à la main au lot précédent sont reprises.

Constat du 08/10/2026 : « Camou Cam » associée à la main à Camille puis fichier
réimporté : la ligne redevenait « Non identifié », et « Enregistrer » l'ignorait
sans le dire. Fixtures inventées.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.modules.schedules.application.timesheet_import import reimport_service
from app.modules.schedules.schemas.ai import (
    AiCalendarProposalResponse,
    AiDayEntry,
    AiEmployeeProposal,
)

pytestmark = pytest.mark.unit

_SERVICE = "app.modules.schedules.application.timesheet_import.reimport_service"


def _jour(jour, heures):
    return AiDayEntry(jour=jour, heures=heures, type="travail", nature="reel")


def _ligne(nom, eid, *, statut=None, jours=None):
    return AiEmployeeProposal(
        raw_name=nom,
        employee_id=eid,
        matched_name=("Camille Dupré" if eid else None),
        match_confidence="high" if eid else "none",
        match_method="name_exact" if eid else "none",
        review_status=statut or ("ok" if eid else "error"),
        days=jours if jours is not None else [_jour(5, 7.0)],
    )


def _proposition(lignes, **kw):
    return AiCalendarProposalResponse(
        year=2026,
        month=10,
        source="test",
        employees=lignes,
        roster_not_in_document_count=kw.get("hors_releve", 0),
        review_summary={"ready": 0, "warning": 0, "error": 0, "empty": 0, "total": len(lignes)},
    )


def _lot(lignes):
    return {
        "id": "lot-ancien",
        "company_id": "co-1",
        "status": "committed",
        "filename": "c1b.csv",
        "file_hash": "h1",
        "summary_json": {},
        "preview_json": _proposition(lignes).model_dump(mode="json"),
    }


def _annoter(proposition, lot):
    deja = [
        {
            "filename": "c1b.csv",
            "file_hash": "h1",
            "lot_precedent": {
                "batch_id": "lot-ancien",
                "fichier": "c1b.csv",
                "filename": "c1b.csv",
                "valide_le": "2026-10-01T16:09:46+00:00",
                "valide_par": "RH Démo",
                "jours_ecrits": 3,
            },
        }
    ]
    with (
        patch(f"{_SERVICE}.timesheet_import_repository") as repo,
        patch(f"{_SERVICE}.schedule_repository") as calendriers,
    ):
        repo.get_batch.return_value = lot
        calendriers.list_schedules_for_employees.return_value = {}
        return reimport_service.annoter_reimport("co-1", proposition, deja)


def test_une_association_manuelle_du_lot_precedent_est_reappliquee():
    lot = _lot([_ligne("Camou Cam", "emp-camille", statut="ok")])
    relue = _proposition([_ligne("Camou  CAM", None)], hors_releve=2)

    annotee, _ = _annoter(relue, lot)

    (ligne,) = annotee.employees
    assert ligne.employee_id == "emp-camille"
    assert ligne.matched_name == "Camille Dupré"
    assert ligne.review_status == "ok"
    assert ligne.match_confidence == "high"
    assert annotee.reimport.associations_reprises == ["Camou  CAM"]
    assert annotee.review_summary["error"] == 0
    assert annotee.review_summary["ready"] == 1
    assert annotee.roster_not_in_document_count == 1


def test_un_nom_inconnu_au_lot_precedent_reste_non_identifie():
    lot = _lot([_ligne("Camou Cam", "emp-camille")])
    relue = _proposition([_ligne("Autre Nom", None)])

    annotee, _ = _annoter(relue, lot)

    assert annotee.employees[0].employee_id is None
    assert annotee.reimport.associations_reprises == []


def test_un_nom_associe_a_deux_salaries_differents_n_est_pas_devine():
    lot = _lot([_ligne("Camou Cam", "emp-1"), _ligne("camou cam", "emp-2")])
    relue = _proposition([_ligne("Camou Cam", None)])

    annotee, _ = _annoter(relue, lot)

    assert annotee.employees[0].employee_id is None


def test_un_salarie_deja_pris_par_une_autre_ligne_n_est_pas_reassigne():
    lot = _lot([_ligne("Camou Cam", "emp-camille")])
    relue = _proposition([_ligne("Camille Dupré", "emp-camille"), _ligne("Camou Cam", None)])

    annotee, _ = _annoter(relue, lot)

    assert annotee.employees[1].employee_id is None
