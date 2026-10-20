"""Ligne absente : maybe_single().execute() rend None (postgrest 2.31), la lecture le dit sans planter.

Même piège que la publication des documents de départ (tournage H.4 du 20/10/2026) :
`.data` était lu sur None. Quand la ligne existe, rien ne change.
"""

from __future__ import annotations

import logging

import pytest

from tests.unit.sans_ligne import sans_ligne  # noqa: F401 — fixture

pytestmark = pytest.mark.unit


def test_une_convention_sans_texte_rend_none(sans_ligne):
    from app.modules.copilot.infrastructure.queries import _get_agreement_text

    client = sans_ligne()
    assert _get_agreement_text(client, "x") is None
