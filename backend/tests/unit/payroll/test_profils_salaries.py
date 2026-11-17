"""La fabrique de profils fait tourner les deux générateurs pour de vrai."""

from __future__ import annotations

import pytest

from tests.unit.payroll.profils_salaries import PROFILS, banc  # noqa: F401

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("profil", PROFILS)
def test_chaque_profil_a_son_bulletin(banc, profil):  # noqa: F811
    donnees = banc.generer(profil)
    assert float(donnees.get("salaire_brut") or 0) > 0
    assert float((donnees.get("net_a_payer") or 0)) > 0
