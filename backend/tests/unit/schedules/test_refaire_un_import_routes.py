"""Refaire un import : les points d'entrée (routes, jobs d'extraction, cache).

Avant le 03/10/2026, seul un tableur déjà validé était refusé ; un PDF déjà
validé était relu et réécrit sans rien dire, corrections à la main comprises
(sur la base de test, une feuille Colorplast importée quatre fois). Désormais
tout fichier déjà importé est refusé avec le lot précédent, et « Refaire
l'import » le relit avec le lecteur actuel, sans resservir l'aperçu en cache.

Supabase moqué, fixtures inventées.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.schedules.application import timesheet_import_service as svc
from app.modules.schedules.schemas.ai import (
    AiCalendarProposalResponse,
    AiDayEntry,
    AiEmployeeProposal,
)

pytestmark = pytest.mark.unit

_SERVICE = "app.modules.schedules.application.timesheet_import.reimport_service"
_PARSE = "app.modules.schedules.application.timesheet_import.parse_service"
_JOBS = "app.modules.schedules.application.timesheet_import_service"

DEJA = b"%PDF-1.4 releve deja valide"
NEUF = b"%PDF-1.4 releve jamais vu"


def _empreinte(contenu: bytes) -> str:
    return hashlib.sha256(contenu).hexdigest()


def _lot_valide():
    return {
        "id": "lot-ancien",
        "status": "committed",
        "filename": "S39.pdf",
        "user_id": "rh-1",
        "completed_at": "2026-10-01T16:09:46+00:00",
        "summary_json": {"committed_days": 47},
    }


def _rh():
    from app.modules.users.schemas.responses import CompanyAccess, User

    return User(
        id="user-rh-1",
        email="rh@test.co",
        first_name="R",
        last_name="H",
        is_platform_admin=False,
        is_group_admin=False,
        accessible_companies=[
            CompanyAccess(company_id="co-1", company_name="Co", role="rh", is_primary=True)
        ],
        active_company_id="co-1",
    )


@pytest.fixture
def en_rh():
    from app.core.security import get_current_user

    app.dependency_overrides[get_current_user] = _rh
    yield
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def lots_en_base():
    """Seul `DEJA` a un lot validé."""
    with patch(f"{_SERVICE}.timesheet_import_repository") as repo:
        repo.lots_valides_du_fichier.side_effect = lambda co, h: (
            [_lot_valide()] if h == _empreinte(DEJA) else []
        )
        repo.nom_utilisateur.return_value = "RH Démo"
        yield repo


class TestRouteUnReleve:
    URL = "/api/schedules/assisted-fill/extract-timesheet/start"

    def _post(self, client, contenu: bytes, **form):
        with (
            patch(f"{_JOBS}.create_import_job", return_value={"id": "job-1"}) as creer,
            patch(f"{_JOBS}.run_timesheet_extraction_job") as lancer,
        ):
            reponse = client.post(
                self.URL,
                files={"file": ("S39.pdf", contenu, "application/pdf")},
                data={"year": "2026", "month": "9", **form},
            )
        return reponse, creer, lancer

    def test_un_releve_deja_importe_est_refuse_avec_le_lot_precedent(
        self, client: TestClient, en_rh, lots_en_base
    ):
        reponse, creer, lancer = self._post(client, DEJA)

        assert reponse.status_code == 409
        detail = reponse.json()["detail"]
        assert detail["code"] == "deja_importe"
        assert "Refaire l'import de ce fichier" in detail["message"]
        (fichier,) = detail["fichiers"]
        assert fichier["filename"] == "S39.pdf"
        assert fichier["lot_precedent"]["batch_id"] == "lot-ancien"
        assert fichier["lot_precedent"]["valide_par"] == "RH Démo"
        creer.assert_not_called()
        lancer.assert_not_called()

    def test_refaire_l_import_lance_la_relecture_avec_le_lot_precedent(
        self, client: TestClient, en_rh, lots_en_base
    ):
        reponse, creer, lancer = self._post(client, DEJA, refaire_import="true")

        assert reponse.status_code == 200
        demande = creer.call_args.kwargs["request_json"]
        (deja,) = demande["reimport"]
        assert deja["file_hash"] == _empreinte(DEJA)
        assert deja["lot_precedent"]["batch_id"] == "lot-ancien"
        lancer.assert_called_once()

    def test_un_releve_jamais_importe_passe_sans_question(
        self, client: TestClient, en_rh, lots_en_base
    ):
        reponse, creer, _ = self._post(client, NEUF)

        assert reponse.status_code == 200
        assert creer.call_args.kwargs["request_json"]["reimport"] == []


class TestRouteImportGroupe:
    URL = "/api/schedules/timesheet-import/extract-timesheet/start-batch"

    def _post(self, client, **form):
        with (
            patch(f"{_JOBS}.create_import_job", return_value={"id": "job-1"}) as creer,
            patch(f"{_JOBS}.run_multi_timesheet_extraction_job") as lancer,
        ):
            reponse = client.post(
                self.URL,
                files=[
                    ("files", ("S38.pdf", NEUF, "application/pdf")),
                    ("files", ("S39.pdf", DEJA, "application/pdf")),
                ],
                data={
                    "year": "2026",
                    "month": "9",
                    "week_anchor_dates": "[null, null]",
                    **form,
                },
            )
        return reponse, creer, lancer

    def test_le_refus_nomme_le_seul_fichier_deja_importe(
        self, client: TestClient, en_rh, lots_en_base
    ):
        reponse, creer, _ = self._post(client)

        assert reponse.status_code == 409
        noms = [f["filename"] for f in reponse.json()["detail"]["fichiers"]]
        assert noms == ["S39.pdf"]
        creer.assert_not_called()

    def test_refaire_l_import_relit_tout_le_lot(self, client: TestClient, en_rh, lots_en_base):
        reponse, creer, lancer = self._post(client, refaire_import="true")

        assert reponse.status_code == 200
        demande = creer.call_args.kwargs["request_json"]
        assert [d["filename"] for d in demande["reimport"]] == ["S39.pdf"]
        lancer.assert_called_once()


class TestRouteTableur:
    def test_la_demande_de_relecture_va_jusqu_au_lecteur(self, client: TestClient, en_rh):
        with patch(f"{_PARSE}.parse_structured_file") as lire:
            lire.return_value = {
                "batch_id": "b1",
                "preview": AiCalendarProposalResponse(year=2026, month=9, source="t"),
            }
            reponse = client.post(
                "/api/schedules/timesheet-import/parse",
                files={"file": ("releve.xlsx", b"PK", "application/octet-stream")},
                data={"year": "2026", "month": "9", "refaire_import": "true"},
            )

        assert reponse.status_code == 200
        assert lire.call_args.kwargs["refaire_import"] is True


# ----- Les jobs d'extraction -----


def _deja():
    return [
        {
            "filename": "S39.pdf",
            "file_hash": _empreinte(DEJA),
            "lot_precedent": {"batch_id": "lot-ancien", "filename": "S39.pdf"},
        }
    ]


def _proposition():
    return AiCalendarProposalResponse(
        year=2026,
        month=9,
        source="test",
        employees=[
            AiEmployeeProposal(
                raw_name="Salarié 0",
                employee_id="emp-1",
                days=[AiDayEntry(jour=15, heures=8.0)],
                match_confidence="high",
            )
        ],
    )


def _job(**request):
    return {
        "id": "job-1",
        "status": "extracting",
        "company_id": "co-1",
        "user_id": "u",
        "filename": "S39.pdf",
        "file_hash": _empreinte(DEJA),
        "request_json": {"year": 2026, "month": 9, "employees": [], **request},
    }


@patch(f"{_JOBS}._job_is_terminal", return_value=False)
@patch(f"{_JOBS}.record_schedule_import_run")
@patch(f"{_JOBS}.create_batch_from_proposal", return_value={"id": "lot-relu"})
@patch(f"{_JOBS}.annoter_reimport")
@patch(f"{_JOBS}._update_job")
@patch(f"{_JOBS}.get_import_job")
def test_le_job_d_un_releve_relu_annote_la_proposition_et_lie_le_lot(
    mock_job, mock_update, mock_annoter, mock_batch, *_
):
    mock_job.return_value = _job(reimport=_deja())
    annotee = _proposition().model_copy(update={"source": "annotée"})
    mock_annoter.return_value = (annotee, {"reimport": True, "previous_committed_batch_id": "lot-ancien"})
    with patch(
        "app.modules.schedules.application.ai_fill.extract_timesheet",
        return_value=_proposition(),
    ):
        svc.run_timesheet_extraction_job("job-1", DEJA)

    company_id, proposition, deja = mock_annoter.call_args.args
    assert (company_id, deja) == ("co-1", _deja())
    assert proposition.employees[0].employee_id == "emp-1"
    assert mock_batch.call_args.kwargs["proposal"] is annotee
    assert mock_batch.call_args.kwargs["extra_summary"]["previous_committed_batch_id"] == "lot-ancien"
    fin = mock_update.call_args_list[-1].args[1]
    assert fin["status"] == "completed"
    assert fin["proposal_json"]["source"] == "annotée"


@patch(f"{_JOBS}._job_is_terminal", return_value=False)
@patch(f"{_JOBS}.record_schedule_import_run")
@patch(f"{_JOBS}.create_batch_from_proposal", return_value={"id": "lot-1"})
@patch(f"{_JOBS}.annoter_reimport")
@patch(f"{_JOBS}._update_job")
@patch(f"{_JOBS}.get_import_job")
def test_un_premier_import_n_est_pas_annote(mock_job, mock_update, mock_annoter, mock_batch, *_):
    mock_job.return_value = _job()
    with patch(
        "app.modules.schedules.application.ai_fill.extract_timesheet",
        return_value=_proposition(),
    ):
        svc.run_timesheet_extraction_job("job-1", NEUF)

    mock_annoter.assert_not_called()
    assert mock_batch.call_args.kwargs.get("extra_summary") is None


@patch(f"{_JOBS}._job_is_terminal", return_value=False)
@patch(f"{_JOBS}._raise_if_job_cancelled")
@patch(f"{_JOBS}.create_batch_from_proposal", return_value={"id": "lot-maitre"})
@patch(f"{_JOBS}.annoter_reimport")
@patch(f"{_JOBS}.parse_with_llm_fallback")
@patch(f"{_JOBS}._update_job")
@patch(f"{_JOBS}.get_import_job")
def test_le_job_groupe_relit_sans_cache_et_lie_le_lot_fusionne(
    mock_job, mock_update, mock_parse, mock_annoter, mock_batch, *_
):
    mock_job.return_value = _job(reimport=_deja())
    mock_parse.side_effect = [(_proposition(), "b1"), (_proposition(), "b2")]
    annotee = _proposition().model_copy(update={"source": "annotée"})
    mock_annoter.return_value = (annotee, {"reimport": True})
    fichiers = [
        svc.FichierAImporter("S38.pdf", NEUF, date(2026, 9, 14)),
        svc.FichierAImporter("S39.pdf", DEJA, date(2026, 9, 21)),
    ]

    svc.run_multi_timesheet_extraction_job("job-1", fichiers)

    assert [appel.kwargs["relire"] for appel in mock_parse.call_args_list] == [True, True]
    assert mock_annoter.call_args.args[2] == _deja()
    assert mock_batch.call_args.kwargs["proposal"] is annotee
    assert mock_batch.call_args.kwargs["extra_summary"] == {"reimport": True}


@patch(f"{_PARSE}.create_batch_from_proposal", return_value={"id": "b"})
@patch(f"{_PARSE}.extract_timesheet")
@patch(f"{_PARSE}.find_cached_preview")
@patch(f"{_PARSE}.enrich_roster_time_tracking_ids", side_effect=lambda r, c: r)
def test_relire_ne_resert_pas_l_apercu_en_cache(mock_roster, mock_cache, mock_extract, _):
    from app.modules.schedules.application.timesheet_import.parse_service import (
        parse_with_llm_fallback,
    )

    mock_cache.return_value = _proposition()
    mock_extract.return_value = _proposition()

    parse_with_llm_fallback(
        company_id="co-1",
        user_id="u",
        content=DEJA,
        filename="S39.pdf",
        year=2026,
        month=9,
        roster=[],
        relire=True,
    )

    mock_cache.assert_not_called()
    mock_extract.assert_called_once()


class TestTableurDejaImporte:
    def _lire(self, *, refaire: bool):
        from app.modules.schedules.application.timesheet_import.parse_service import (
            parse_structured_file,
        )

        attempt = MagicMock(parser_key="tabular_generic", parse_result=None, warnings=[])
        with (
            patch(f"{_PARSE}.find_cached_preview") as cache,
            patch(f"{_PARSE}.enrich_roster_time_tracking_ids", side_effect=lambda r, c: r),
            patch(f"{_PARSE}.parse_document", return_value=attempt),
            patch(f"{_PARSE}.build_proposal_from_attempt", return_value=_proposition()),
            patch(
                "app.modules.schedules.application.ai_fill._finalize_timesheet_proposal",
                side_effect=lambda p, **k: p,
            ),
            patch(f"{_PARSE}.upload_schedule_import_file", return_value="chemin"),
            patch(f"{_PARSE}.create_batch_from_proposal", return_value={"id": "lot-relu"}) as lot,
            patch(f"{_PARSE}.annoter_reimport") as annoter,
            patch(f"{_PARSE}.timesheet_import_repository"),
        ):
            annoter.return_value = (_proposition(), {"reimport": True})
            resultat = parse_structured_file(
                company_id="co-1",
                user_id="u",
                content=DEJA,
                filename="releve.csv",
                year=2026,
                month=9,
                roster=[],
                refaire_import=refaire,
            )
        return resultat, cache, lot, annoter

    def test_un_tableur_deja_importe_est_refuse_avec_le_lot_precedent(self, lots_en_base):
        from app.modules.schedules.application.exceptions import ScheduleAppError

        with pytest.raises(ScheduleAppError) as refus:
            self._lire(refaire=False)

        assert refus.value.status_code == 409
        assert refus.value.detail["code"] == "deja_importe"
        assert "déjà été importé" in refus.value.message

    def test_refaire_l_import_relit_le_tableur_et_lie_le_lot(self, lots_en_base):
        _, cache, lot, annoter = self._lire(refaire=True)

        cache.assert_not_called()
        assert annoter.call_args.args[2][0]["lot_precedent"]["batch_id"] == "lot-ancien"
        assert lot.call_args.kwargs["extra_summary"] == {"reimport": True}


def test_le_refus_structure_arrive_tel_quel_au_front():
    from fastapi import HTTPException

    from app.modules.schedules.api.router import _handle_schedule_error
    from app.modules.schedules.application.exceptions import ScheduleAppError

    detail = {"code": "deja_importe", "message": "déjà importé", "fichiers": []}
    with pytest.raises(HTTPException) as http:
        _handle_schedule_error(ScheduleAppError("validation", "déjà importé", 409, detail))
    assert http.value.detail == detail

    with pytest.raises(HTTPException) as http:
        _handle_schedule_error(ScheduleAppError("validation", "phrase", 400))
    assert http.value.detail == "phrase"
    assert json.dumps(detail)
