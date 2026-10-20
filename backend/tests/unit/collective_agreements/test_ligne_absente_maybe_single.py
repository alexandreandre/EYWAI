"""Ligne absente : maybe_single().execute() rend None (postgrest 2.31), la lecture le dit sans planter.

Même piège que la publication des documents de départ (tournage H.4 du 20/10/2026) :
`.data` était lu sur None. Quand la ligne existe, rien ne change.
"""

from __future__ import annotations

import logging

import pytest

from tests.unit.sans_ligne import sans_ligne  # noqa: F401 — fixture

pytestmark = pytest.mark.unit


def test_un_journal_d_extraction_disparu_se_lit_comme_absent(sans_ligne):
    from app.modules.collective_agreements.rules.repository import CCRulesRepository

    client = sans_ligne()
    assert CCRulesRepository(client).get_log_by_id("x") is None


def test_une_recommandation_disparue_se_lit_comme_absente(sans_ligne):
    from app.modules.collective_agreements.training_reco import repository

    sans_ligne(repository)
    assert repository.CcTrainingRecommendationsRepository().get_by_id("x") is None


def test_une_convention_sans_grille_rend_une_liste_vide(sans_ligne):
    from app.modules.collective_agreements.infrastructure.queries import (
        get_classifications_for_idcc,
    )

    client = sans_ligne()
    assert get_classifications_for_idcc(client, "1234") == []


def test_une_convention_sans_idcc_rend_none(sans_ligne):
    from app.modules.collective_agreements.application.idcc_resolution import (
        get_idcc_for_agreement,
    )

    client = sans_ligne()
    assert get_idcc_for_agreement("x", client) is None
