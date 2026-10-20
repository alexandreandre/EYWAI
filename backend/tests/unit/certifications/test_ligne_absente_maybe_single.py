"""Ligne absente : maybe_single().execute() rend None (postgrest 2.31), la lecture le dit sans planter.

Même piège que la publication des documents de départ (tournage H.4 du 20/10/2026) :
`.data` était lu sur None. Quand la ligne existe, rien ne change.
"""

from __future__ import annotations

import logging

import pytest

from tests.unit.sans_ligne import sans_ligne  # noqa: F401 — fixture

pytestmark = pytest.mark.unit


def test_un_salarie_hors_societe_est_refuse_avec_son_message(sans_ligne):
    from app.modules.certifications.application import commands

    sans_ligne(commands)
    with pytest.raises(ValueError, match="Employé introuvable"):
        commands._assert_employee_in_company("x", "c")
