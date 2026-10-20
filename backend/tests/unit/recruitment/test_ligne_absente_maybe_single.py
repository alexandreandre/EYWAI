"""Ligne absente : maybe_single().execute() rend None (postgrest 2.31), la lecture le dit sans planter.

Même piège que la publication des documents de départ (tournage H.4 du 20/10/2026) :
`.data` était lu sur None. Quand la ligne existe, rien ne change.
"""

from __future__ import annotations

import logging

import pytest

from tests.unit.sans_ligne import sans_ligne  # noqa: F401 — fixture

pytestmark = pytest.mark.unit


def test_les_lectures_du_recrutement_rendent_none_sans_ligne(sans_ligne):
    from app.modules.recruitment.infrastructure import queries, repository

    sans_ligne(queries, repository)
    assert queries.get_candidate("c", "x") is None
    assert queries.get_candidate_with_stage_position("c", "x") is None
    assert queries.get_candidate_email_phone("c", "x") is None
    assert repository.JobRepository().get_by_id("c", "x") is None
    assert repository.PipelineStageRepository().get_by_id("c", "x") is None


def test_un_cv_ou_un_audio_pour_un_candidat_disparu_est_refuse(sans_ligne):
    from app.modules.recruitment.infrastructure import repository

    sans_ligne(repository)
    with pytest.raises(ValueError, match="Candidat non trouvé"):
        repository.CandidateRepository().upload_cv("x", "c", b"%PDF", "cv.pdf", "application/pdf")
    with pytest.raises(ValueError, match="Candidat non trouvé"):
        repository.NoteRepository().upload_audio("x", "c", b"son", "note.webm")
