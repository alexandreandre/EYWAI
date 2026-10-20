"""Ligne absente : maybe_single().execute() rend None (postgrest 2.31), la lecture le dit sans planter.

Même piège que la publication des documents de départ (tournage H.4 du 20/10/2026) :
`.data` était lu sur None. Quand la ligne existe, rien ne change.
"""

from __future__ import annotations

import logging

import pytest

from tests.unit.sans_ligne import sans_ligne  # noqa: F401 — fixture

pytestmark = pytest.mark.unit


def test_le_contrat_de_pret_sans_societe_ni_salarie_le_dit(sans_ligne):
    from app.modules.employee_loans.application import commands

    sans_ligne()
    with pytest.raises(LookupError, match="introuvables"):
        commands._fetch_contract_parties("c", "e")
