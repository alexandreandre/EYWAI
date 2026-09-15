"""Compteurs d'heures du bulletin : « Cumul heures » et « Cumul h. sup ».

Retour de Gaëlle : le cumul d'heures imprimé est faux. Il l'est de deux façons,
relevées sur les bulletins du cabinet de Colorplast de janvier 2026 :

* **les heures sup conjoncturelles n'y sont pas.** Bugny 169,00 chez nous contre
  189,50 chez le cabinet — exactement les 12 h à 25 % et 8,5 h à 50 % du mois.
  Espinosa 169,00 contre 185,00. Les trois salariés sans heures sup
  conjoncturelles tombaient juste, ce qui masquait le défaut ;
* **les heures sup perdues par une absence ne sont pas retranchées du compteur
  d'heures sup.** Cotte 17,33 chez nous contre 16,97, Gautheron 17,33 contre
  16,20 : la part « heures sup structurelles » de leur absence.

Le premier défaut ne touche pas que l'impression. Le cumul d'heures rémunérées
sert de point de départ au SMIC de référence de la réduction générale du mois
suivant (`_lire_cumuls_precedents`). Le moteur calculait la réduction de janvier
sur 189,50 h mais n'en mémorisait que 169,00 : dès février, le SMIC de référence
cumulé repartait 20,50 h trop bas pour Bugny, et la réduction avec lui. Les deux
figures sont désormais la même.

Chiffres repris des bulletins de janvier 2026 (env. de test).
"""

from __future__ import annotations

from datetime import date

import pytest

from app.modules.payroll.engine.calcul_brut import calculer_salaire_brut

from .helpers import build_test_contexte

pytestmark = pytest.mark.unit

JANVIER = (date(2026, 1, 1), date(2026, 1, 31))
#: 151,67 h légales mensualisées.
BASE_LEGALE = 151.67


def _calendrier(absences=None, hs=None, heures_jour=8.5):
    cal = []
    jour = date(2026, 1, 1)
    while jour.month == 1:
        if jour.weekday() < 5:
            iso = jour.isoformat()
            manque = (absences or {}).get(iso, 0.0)
            if manque < heures_jour:
                cal.append({"date_complete": iso, "type": "travail_base",
                            "heures": heures_jour - manque})
            if manque > 0:
                cal.append({"date_complete": iso, "type": "absence_injustifiee_base",
                            "heures": manque})
        jour = date.fromordinal(jour.toordinal() + 1)
    for iso, (type_ev, heures) in (hs or {}).items():
        cal.append({"date_complete": iso, "type": type_ev, "heures": heures})
    return cal


def _compteurs(res):
    """Les deux compteurs, composés comme `payslip_run_heures` les enregistre."""
    cumul_hs = round(res["total_heures_supp"] - res["heures_sup_perdues_absence"], 2)
    cumul_heures = round(
        BASE_LEGALE
        + res["total_heures_supp"]
        + res["heures_complementaires"]
        - res["heures_absence_non_payees"],
        2,
    )
    return cumul_heures, cumul_hs


class TestCumulHeures:
    def test_bugny_les_heures_sup_conjoncturelles_comptent(self):
        ctx = build_test_contexte(salaire_base=2123.38, duree_hebdo=39.0)
        cal = _calendrier(hs={
            "2026-01-15": ("travail_hs25", 12.0),
            "2026-01-16": ("travail_hs50", 8.5),
        })
        heures, hs = _compteurs(calculer_salaire_brut(ctx, cal, *JANVIER, []))
        assert heures == pytest.approx(189.50, abs=0.01)
        assert hs == pytest.approx(37.83, abs=0.01)

    def test_espinosa(self):
        ctx = build_test_contexte(salaire_base=2328.0, duree_hebdo=39.0)
        cal = _calendrier(hs={
            "2026-01-15": ("travail_hs25", 12.0),
            "2026-01-16": ("travail_hs50", 4.0),
        })
        heures, hs = _compteurs(calculer_salaire_brut(ctx, cal, *JANVIER, []))
        assert heures == pytest.approx(185.00, abs=0.01)
        assert hs == pytest.approx(33.33, abs=0.01)

    def test_girerd_sans_heures_sup_conjoncturelles_rien_ne_bouge(self):
        ctx = build_test_contexte(salaire_base=3101.0, duree_hebdo=39.0)
        heures, hs = _compteurs(calculer_salaire_brut(ctx, _calendrier(), *JANVIER, []))
        assert heures == pytest.approx(169.00, abs=0.01)
        assert hs == pytest.approx(17.33, abs=0.01)


class TestCumulHeuresSupEtAbsences:
    def test_cotte_une_absence_de_3h30(self):
        ctx = build_test_contexte(salaire_base=1964.0, duree_hebdo=39.0)
        cal = _calendrier(absences={"2026-01-21": 3.5})
        res = calculer_salaire_brut(ctx, cal, *JANVIER, [])
        # 3,5 h réparties 35/39 : 0,36 h retirée des heures sup structurelles.
        assert res["heures_sup_perdues_absence"] == pytest.approx(0.36, abs=0.01)
        heures, hs = _compteurs(res)
        assert heures == pytest.approx(165.50, abs=0.01)
        assert hs == pytest.approx(16.97, abs=0.01)

    def test_gautheron_deux_absences(self):
        ctx = build_test_contexte(salaire_base=1964.0, duree_hebdo=39.0)
        cal = _calendrier(absences={"2026-01-13": 2.5, "2026-01-14": 8.5})
        res = calculer_salaire_brut(ctx, cal, *JANVIER, [])
        assert res["heures_sup_perdues_absence"] == pytest.approx(1.13, abs=0.01)
        heures, hs = _compteurs(res)
        assert heures == pytest.approx(158.00, abs=0.01)
        assert hs == pytest.approx(16.20, abs=0.01)

    def test_sans_absence_rien_n_est_retranche(self):
        ctx = build_test_contexte(salaire_base=2123.38, duree_hebdo=39.0)
        res = calculer_salaire_brut(ctx, _calendrier(), *JANVIER, [])
        assert res["heures_sup_perdues_absence"] == 0.0
