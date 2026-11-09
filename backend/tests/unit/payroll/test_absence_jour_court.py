"""Une journée d'absence sur un jour planifié moins de 7 h (R-282).

Vendredi de 5 h non payé : Martine retire 5 h, Quadra 7 h. Retenir au-delà du
temps non travaillé revient à une sanction pécuniaire, interdite (C. trav.
L1331-2) ; la retenue suit strictement le temps d'absence (Cass. soc.
11/02/1982, n° 80-40359, lue sur LégiSocial, Légifrance étant fermé).
"""

from datetime import date

import pytest

from app.modules.payroll.engine.calcul_brut import calculer_salaire_brut

from .helpers import build_test_contexte

pytestmark = pytest.mark.unit

JUILLET = (date(2026, 7, 1), date(2026, 7, 31))
#: Le vendredi 10 juillet : journée planifiée de 5 h, contrat de 35 h.
VENDREDI = "2026-07-10"


def _calendrier(absence_heures: float) -> list[dict]:
    cal = []
    jour = date(2026, 7, 1)
    while jour.month == 7:
        if jour.weekday() < 5:
            iso = jour.isoformat()
            planifie = 5.0 if jour.weekday() == 4 else 7.5
            if iso == VENDREDI:
                cal.append({"date_complete": iso, "type": "absence_injustifiee_base", "heures": absence_heures})
            else:
                cal.append({"date_complete": iso, "type": "travail_base", "heures": planifie})
        jour = date.fromordinal(jour.toordinal() + 1)
    return cal


def test_un_vendredi_de_5_h_non_paye_retire_5_h_et_non_7():
    ctx = build_test_contexte(salaire_base=2000.0, duree_hebdo=35.0)
    res = calculer_salaire_brut(ctx, _calendrier(5.0), *JUILLET, [])
    lignes = [l for l in res["lignes_composants_brut"] if "Absence injustifiée" in str(l.get("libelle"))]
    assert [l["quantite"] for l in lignes] == [5.0]
