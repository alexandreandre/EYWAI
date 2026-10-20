"""Ligne absente : maybe_single().execute() rend None (postgrest 2.31), la lecture le dit sans planter.

Même piège que la publication des documents de départ (tournage H.4 du 20/10/2026) :
`.data` était lu sur None. Quand la ligne existe, rien ne change.
"""

from __future__ import annotations

import logging

import pytest

from tests.unit.sans_ligne import sans_ligne  # noqa: F401 — fixture

pytestmark = pytest.mark.unit


def test_un_webhook_disparu_est_absent_sans_erreur_journalisee(sans_ligne, caplog):
    from app.modules.webhooks.infrastructure import repository

    sans_ligne(repository)
    with caplog.at_level(logging.ERROR):
        assert repository.WebhookRepository().get_by_id("x", "c") is None
    assert not [r for r in caplog.records if r.levelno >= logging.ERROR]
