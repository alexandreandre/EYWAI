"""Premier mois après une reprise : les absences datées jusqu'à la bascule ont été
traitées par l'ancien logiciel, les heures sup de ces jours-là non.

Colorplast, septembre 2026 (bascule au 31/08, fenêtre du 24/08 au 20/09) : Quadra a
mis en congés sans solde sur août les demi-journées du 24 et du 28/08 d'un salarié ;
septembre les recomptait en congés payés. Les heures sup de la semaine 35, elles,
sont payées en septembre.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.modules.payroll.engine.calcul_brut import calculer_salaire_brut

from .helpers import build_test_contexte

pytestmark = pytest.mark.unit


def _evenement(jour, mois, type_ev, heures):
    return {"annee": 2026, "mois": mois, "jour": jour, "date_complete": f"2026-{mois:02d}-{jour:02d}",
            "type": type_ev, "heures": heures}


def _calcul(fin_de_la_reprise):
    ctx = build_test_contexte(duree_hebdo=35.0)
    ctx.fin_de_la_reprise = fin_de_la_reprise
    calendrier = [
        _evenement(27, 8, "travail_hs25", 3.0),
        _evenement(28, 8, "conges_payes", 7.0),
        _evenement(31, 8, "absence_non_remuneree", 7.0),
        _evenement(4, 9, "conges_payes", 7.0),
    ]
    return calculer_salaire_brut(
        ctx, calendrier, date(2026, 9, 1), date(2026, 9, 30), [],
        date_debut_variables=date(2026, 8, 24), date_fin_variables=date(2026, 9, 20),
    )


def _libelles(resultat):
    return [str(l.get("libelle")) for l in resultat["lignes_composants_brut"]]


def test_les_absences_d_avant_la_bascule_ne_reviennent_pas():
    resultat = _calcul(date(2026, 8, 31))
    conges = [l for l in _libelles(resultat) if l.startswith("Absence congés payés")]
    assert conges and "28/08" not in conges[0] and "04/09" in conges[0]
    assert not any(l.startswith("Absence non rémunérée du 31/08") for l in _libelles(resultat))


def test_les_heures_sup_d_avant_la_bascule_restent_payees():
    assert _calcul(date(2026, 8, 31))["total_heures_supp"] == pytest.approx(3.0)


def test_sans_reprise_rien_ne_change():
    libelles = _libelles(_calcul(None))
    assert any("28/08" in l for l in libelles if l.startswith("Absence congés payés"))
    assert any(l.startswith("Absence non rémunérée du 31/08") for l in libelles)
