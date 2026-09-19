"""Import groupé de pointages : chaque fichier porte sa semaine.

Le dialogue accepte plusieurs feuilles et un sélecteur « Semaine (optionnel) »
par fichier ; le job groupé doit extraire chaque fichier avec sa semaine — il
ignorait la semaine —, nommer la semaine dans sa progression, et dire quand
deux fichiers portent la même (la fusion garde le dernier sur les jours communs).
"""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from app.modules.schedules.application import timesheet_import_service as svc

pytestmark = pytest.mark.unit


# --- 1. Parties pures --------------------------------------------------------


def test_les_semaines_sont_lues_dans_l_ordre_des_fichiers():
    assert svc.semaines_alignees('["2026-07-06", null, "2026-07-20"]', 3) == [
        date(2026, 7, 6), None, date(2026, 7, 20)
    ]


def test_sans_liste_aucune_semaine():
    assert svc.semaines_alignees(None, 2) == [None, None]
    assert svc.semaines_alignees("", 2) == [None, None]


def test_une_liste_desalignee_est_refusee():
    with pytest.raises(ValueError, match="une entrée par fichier"):
        svc.semaines_alignees('["2026-07-06"]', 2)


def test_une_date_illisible_est_refusee():
    with pytest.raises(ValueError, match="AAAA-MM-JJ"):
        svc.semaines_alignees('["06/07/2026"]', 1)


def test_le_libelle_nomme_la_semaine():
    f = svc.FichierAImporter("s28.pdf", b"x", date(2026, 7, 6))
    assert svc.libelle_fichier(f) == "S28 · s28.pdf"
    assert svc.libelle_fichier(svc.FichierAImporter("libre.pdf", b"x")) == "libre.pdf"


def test_deux_fichiers_sur_la_meme_semaine_sont_signales():
    fichiers = [
        svc.FichierAImporter("a.pdf", b"x", date(2026, 7, 6)),
        svc.FichierAImporter("b.pdf", b"x", date(2026, 7, 6)),
        svc.FichierAImporter("c.pdf", b"x", date(2026, 7, 13)),
    ]
    avertissements = svc.avertissement_semaines_en_double(fichiers)
    assert avertissements == [
        "S28 : deux fichiers (a.pdf, b.pdf) — le dernier écrase le premier sur les jours communs."
    ]
    assert svc.avertissement_semaines_en_double(fichiers[1:]) == []


# --- 2. Le job groupé --------------------------------------------------------


def _proposition(nom: str):
    p = MagicMock()
    p.employees = []
    p.warnings = []
    p.model_copy.return_value = p
    p.model_dump.return_value = {"source": nom}
    return p


def _job(**request):
    return {
        "id": "job-1", "status": "extracting", "company_id": "co", "user_id": "u",
        "request_json": {"year": 2026, "month": 7, "employees": [], **request},
    }


@patch(f"{svc.__name__}._job_is_terminal", return_value=False)
@patch(f"{svc.__name__}._raise_if_job_cancelled")
@patch(f"{svc.__name__}.create_batch_from_proposal", return_value={"id": "batch-maitre"})
@patch(f"{svc.__name__}.parse_with_llm_fallback")
@patch(f"{svc.__name__}._update_job")
@patch(f"{svc.__name__}.get_import_job")
def test_chaque_fichier_est_extrait_avec_sa_semaine(mock_job, mock_update, mock_parse, *_):
    mock_job.return_value = _job(single_employee=False, document_scope="weekly")
    mock_parse.side_effect = [(_proposition("a"), "b1"), (_proposition("b"), "b2")]
    fichiers = [
        svc.FichierAImporter("s28.pdf", b"1", date(2026, 7, 6)),
        svc.FichierAImporter("s29.pdf", b"2", date(2026, 7, 13)),
    ]

    svc.run_multi_timesheet_extraction_job("job-1", fichiers)

    semaines = [appel.kwargs["week_anchor_date"] for appel in mock_parse.call_args_list]
    assert semaines == [date(2026, 7, 6), date(2026, 7, 13)]
    libelles = [
        appel.args[1]["progress_json"]["current_file"]
        for appel in mock_update.call_args_list
        if "current_file" in appel.args[1].get("progress_json", {})
    ]
    assert libelles == ["S28 · s28.pdf", "S29 · s29.pdf"]


@patch(f"{svc.__name__}._job_is_terminal", return_value=False)
@patch(f"{svc.__name__}._raise_if_job_cancelled")
@patch(f"{svc.__name__}.create_batch_from_proposal", return_value={"id": "batch-maitre"})
@patch(f"{svc.__name__}.parse_with_llm_fallback")
@patch(f"{svc.__name__}._update_job")
@patch(f"{svc.__name__}.get_import_job")
def test_la_meme_semaine_deux_fois_est_signalee_dans_la_proposition(
    mock_job, mock_update, mock_parse, mock_batch, *_
):
    mock_job.return_value = _job()
    mock_parse.side_effect = [(_proposition("a"), "b1"), (_proposition("b"), "b2")]
    fichiers = [svc.FichierAImporter(n, b"x", date(2026, 7, 6)) for n in ("a.pdf", "b.pdf")]

    svc.run_multi_timesheet_extraction_job("job-1", fichiers)

    fusion = mock_batch.call_args.kwargs["proposal"]
    avertissements = fusion.model_copy.call_args.kwargs["update"]["warnings"]
    assert any("S28 : deux fichiers" in w for w in avertissements)
