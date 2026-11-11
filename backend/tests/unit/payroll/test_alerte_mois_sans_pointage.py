"""R17 (périmètre d'Elsa, 11/11/2026) : sans pointage, Martine paie le prévu et le dit."""

from __future__ import annotations

import pytest

from app.modules.payroll.planning_repli import (
    CODE_ALERTE_MOIS_SANS_POINTAGE,
    alerte_mois_sans_pointage,
    reel_heures_avec_repli_planning_si_sans_pointage,
)

pytestmark = pytest.mark.unit

_PREVU = [
    {"annee": 2026, "mois": 11, "jour": j, "type": "travail", "heures_prevues": 7.0}
    for j in (2, 3, 4)
]


def test_mois_sans_pointage_porte_l_alerte():
    reel = reel_heures_avec_repli_planning_si_sans_pointage(_PREVU, [], annee=2026, mois=11)
    alerte = alerte_mois_sans_pointage(reel, annee=2026, mois=11)
    assert alerte is not None
    assert alerte["code"] == CODE_ALERTE_MOIS_SANS_POINTAGE
    assert alerte["critique"] is False
    assert "3 jour(s)" in alerte["message"] and "11/2026" in alerte["message"]


def test_mois_pointe_sans_alerte():
    reel = [{"annee": 2026, "mois": 11, "jour": 2, "type": "travail", "heures_faites": 7.0}]
    apres = reel_heures_avec_repli_planning_si_sans_pointage(_PREVU, reel, annee=2026, mois=11)
    assert alerte_mois_sans_pointage(apres, annee=2026, mois=11) is None


def test_repli_du_mois_precedent_ne_compte_pas():
    reel = [{"annee": 2026, "mois": 10, "jour": 30, "type": "travail", "heures_faites": 7.0,
             "source_repli_planning": True}]
    assert alerte_mois_sans_pointage(reel, annee=2026, mois=11) is None
