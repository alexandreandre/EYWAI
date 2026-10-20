"""Ligne absente : maybe_single().execute() rend None (postgrest 2.31), la lecture le dit sans planter.

Même piège que la publication des documents de départ (tournage H.4 du 20/10/2026) :
`.data` était lu sur None. Quand la ligne existe, rien ne change.
"""

from __future__ import annotations

import logging

import pytest

from tests.unit.sans_ligne import sans_ligne  # noqa: F401 — fixture

pytestmark = pytest.mark.unit


def test_un_ticket_disparu_se_lit_comme_absent(sans_ligne):
    from app.modules.support.infrastructure import repository

    sans_ligne(repository)
    depot = repository.SupabaseSupportRepository()
    assert depot.get_by_id("x") is None
    assert depot.update_status("x", "resolu") is None
