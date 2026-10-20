"""Ligne absente : maybe_single().execute() rend None (postgrest 2.31), la lecture le dit sans planter.

Même piège que la publication des documents de départ (tournage H.4 du 20/10/2026) :
`.data` était lu sur None. Quand la ligne existe, rien ne change.
"""

from __future__ import annotations

import logging

import pytest

from tests.unit.sans_ligne import sans_ligne  # noqa: F401 — fixture

pytestmark = pytest.mark.unit


def test_une_source_sans_travail_n_a_pas_de_dernier_travail(sans_ligne):
    from app.modules.scraping.infrastructure import repository

    sans_ligne(repository)
    assert repository.ScrapingRepository().get_last_job_for_source("x") is None
