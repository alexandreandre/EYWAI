"""SMIC de référence de la réduction générale : les heures d'absence non
rémunérée doivent en sortir.

Le SMIC de référence est proportionnel aux heures rémunérées. EYWAI partait
des heures contractuelles (151,67 + heures sup structurelles) augmentées des
heures sup conjoncturelles, sans jamais retrancher les heures d'absence non
rémunérée : le SMIC de référence était trop élevé, donc la réduction trop
forte.

Colorplast, janvier 2026, contrats 39 h (audit du 14/09,
`docs/colorplast-janvier-2026-ligne-a-ligne.md`) :

* Léo Cotte, absence de 3,5 h le 21/01 → 169,00 h utilisées au lieu de
  165,50 ; réduction 643,01 au lieu des 609,61 de Quadra ;
* Marion Gautheron, absences de 2,5 h le 13/01 et 8,5 h le 14/01 → 169,00 h
  au lieu de 158,00 ; réduction 689,65 au lieu des 582,21 de Quadra.

Les trois salariés sans absence (Bugny, Espinosa, Girerd) tombent déjà au
centime : la correction ne doit pas les bouger.

L'arrêt maladie est hors périmètre : la rémunération y est maintenue en tout
ou partie, le SMIC de référence suit alors la part restée à la charge de
l'employeur (règle distincte, sans référence cabinet à ce jour).
"""

from __future__ import annotations

from datetime import date

import pytest

from app.modules.payroll.engine.calcul_brut import calculer_salaire_brut

from .helpers import build_test_contexte

pytestmark = pytest.mark.unit

JANVIER = (date(2026, 1, 1), date(2026, 1, 31))
#: 151,67 h légales + 17,33 h sup structurelles mensualisées d'un contrat 39 h.
HEURES_CONTRAT_39H = 169.0


def _calendrier(absences: dict[str, float], *, type_absence: str = "absence_injustifiee_base",
                heures_jour: float = 8.5) -> list[dict]:
    """Janvier ouvré à 8,5 h, avec les absences demandées (jour ISO → heures)."""
    cal: list[dict] = []
    jour = date(2026, 1, 1)
    while jour.month == 1:
        if jour.weekday() < 5:
            iso = jour.isoformat()
            manque = absences.get(iso, 0.0)
            if manque < heures_jour:
                cal.append({"date_complete": iso, "type": "travail_base",
                            "heures": heures_jour - manque})
            if manque > 0:
                cal.append({"date_complete": iso, "type": type_absence, "heures": manque})
        jour = date.fromordinal(jour.toordinal() + 1)
    return cal


def _heures_smic_reference(res: dict) -> float:
    """Heures rémunérées servant au SMIC de référence, telles que les assemble
    `payslip_run_heures` : base légale + heures sup − absences non payées."""
    return round(
        HEURES_CONTRAT_39H
        + res["heures_sup_conjoncturelles"]
        - res["heures_absence_non_payees"],
        2,
    )


class TestHeuresAbsenceExposees:
    def test_sans_absence_rien_a_retrancher(self):
        ctx = build_test_contexte(salaire_base=2123.38, duree_hebdo=39.0)
        res = calculer_salaire_brut(ctx, _calendrier({}), *JANVIER, [])
        assert res["heures_absence_non_payees"] == 0.0
        assert _heures_smic_reference(res) == HEURES_CONTRAT_39H

    def test_cotte_une_absence_de_3h30(self):
        # 3,5 h réparties 35/39 : 3,14 en base + 0,36 sur les HS structurelles.
        ctx = build_test_contexte(salaire_base=1964.0, duree_hebdo=39.0)
        res = calculer_salaire_brut(ctx, _calendrier({"2026-01-21": 3.5}), *JANVIER, [])
        assert res["heures_absence_non_payees"] == pytest.approx(3.50, abs=0.005)
        assert _heures_smic_reference(res) == pytest.approx(165.50, abs=0.005)

    def test_gautheron_deux_absences(self):
        # 2,5 h → 2,24 + 0,26 ; 8,5 h → 7,63 + 0,87. Total 11,00 h.
        ctx = build_test_contexte(salaire_base=1964.0, duree_hebdo=39.0)
        cal = _calendrier({"2026-01-13": 2.5, "2026-01-14": 8.5})
        res = calculer_salaire_brut(ctx, cal, *JANVIER, [])
        assert res["heures_absence_non_payees"] == pytest.approx(11.00, abs=0.005)
        assert _heures_smic_reference(res) == pytest.approx(158.00, abs=0.005)

    def test_absence_non_remuneree_compte_aussi(self):
        ctx = build_test_contexte(salaire_base=1964.0, duree_hebdo=39.0)
        cal = _calendrier({"2026-01-21": 8.5}, type_absence="absence_non_remuneree")
        res = calculer_salaire_brut(ctx, cal, *JANVIER, [])
        assert res["heures_absence_non_payees"] == pytest.approx(8.50, abs=0.005)

    def test_arret_maladie_hors_perimetre(self):
        # La rémunération est maintenue en tout ou partie : règle distincte.
        ctx = build_test_contexte(salaire_base=1964.0, duree_hebdo=39.0)
        cal = _calendrier({"2026-01-21": 8.5}, type_absence="arret_maladie")
        res = calculer_salaire_brut(ctx, cal, *JANVIER, [])
        assert res["heures_absence_non_payees"] == 0.0

    def test_les_heures_sup_conjoncturelles_s_ajoutent(self):
        # Bugny : 12 h à 25 % et 8,5 h à 50 % → 189,50 h, inchangé.
        ctx = build_test_contexte(salaire_base=2123.38, duree_hebdo=39.0)
        cal = _calendrier({})
        cal.append({"date_complete": "2026-01-15", "type": "travail_hs25", "heures": 12.0})
        cal.append({"date_complete": "2026-01-16", "type": "travail_hs50", "heures": 8.5})
        res = calculer_salaire_brut(ctx, cal, *JANVIER, [])
        assert res["heures_absence_non_payees"] == 0.0
        assert _heures_smic_reference(res) == pytest.approx(189.50, abs=0.005)
