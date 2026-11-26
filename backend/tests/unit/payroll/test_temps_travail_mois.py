"""Tests unitaires — temps payé du mois (prorata de la prime d'ancienneté, CCN métallurgie art. 142).

ratio = 1 − temps non payé ÷ référence, plus heures sup × (1 + majoration) ÷ référence.
Les cas de bout en bout, aux deux générateurs : `test_prime_anciennete_temps_paye.py`.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.modules.payroll.engine.temps_travail_mois import (
    TempsDuMois,
    jours_ouvres_hors_feries,
    ratio_du_temps_paye,
    reference_heures_du_contrat,
)

pytestmark = pytest.mark.unit


def _heures(**kw) -> TempsDuMois:
    return TempsDuMois(unite="heures", reference=151.67, **kw)


def test_mois_sans_absence_ratio_un():
    assert ratio_du_temps_paye(_heures()).ratio == 1.0


def test_absences_non_payees_activite_partielle_et_hors_contrat_s_additionnent():
    res = ratio_du_temps_paye(_heures(absences_non_payees=7.0, activite_partielle=14.0, hors_contrat=21.0))
    assert res.ratio == round((151.67 - 42) / 151.67, 6)
    assert res.detail["activite_partielle"] == 14.0


def test_absence_injustifiee_22_92_h():
    assert round(ratio_du_temps_paye(_heures(absences_non_payees=22.92)).ratio, 4) == 0.8489


def test_heures_sup_majorees_s_ajoutent():
    res = ratio_du_temps_paye(_heures(heures_sup_majorees=5.25 * 1.25))
    assert res.ratio == round(1 + 5.25 * 1.25 / 151.67, 6)


def test_heures_sup_ignorees_si_la_regle_les_exclut():
    res = ratio_du_temps_paye(_heures(heures_sup_majorees=10.0), inclure_heures_sup=False)
    assert res.ratio == 1.0


def test_arret_maintenu_reste_paye_le_non_maintenu_retire_sa_journee():
    arret = tuple((date(2026, 4, d), 7.0) for d in (15, 16, 17))
    assert ratio_du_temps_paye(_heures(jours_arret=arret), jours_maintien={15, 16, 17}).ratio == 1.0
    res = ratio_du_temps_paye(_heures(jours_arret=arret), jours_maintien={16, 17})
    assert res.ratio == round(144.67 / 151.67, 6)
    assert res.detail["arret_non_maintenu"] == 7.0


def test_arret_maintenu_retire_si_la_regle_ne_le_compte_pas():
    arret = ((date(2026, 4, 15), 7.0),)
    res = ratio_du_temps_paye(_heures(jours_arret=arret), jours_maintien={15}, maladie_si_maintien=False)
    assert res.ratio == round(144.67 / 151.67, 6)


def test_ratio_borne_a_zero_mois_entierement_non_paye():
    assert ratio_du_temps_paye(_heures(absences_non_payees=160.0)).ratio == 0.0


def test_plafond_du_ratio():
    assert ratio_du_temps_paye(_heures(heures_sup_majorees=20.0), ratio_plafond=1.0).ratio == 1.0


def test_forfait_en_jours():
    temps = TempsDuMois(unite="jours", reference=19.0, activite_partielle=2.0)
    assert ratio_du_temps_paye(temps).ratio == round(17 / 19, 6)


def test_reference_du_contrat():
    assert reference_heures_du_contrat(35) == 151.67
    assert reference_heures_du_contrat(39) == 169.0
    assert reference_heures_du_contrat(0) == 151.67


def test_jours_ouvres_hors_feries():
    jours = jours_ouvres_hors_feries(date(2026, 11, 2), date(2026, 11, 27), {date(2026, 11, 11), date(2026, 11, 1)})
    assert len(jours) == 19


def test_temps_partiel_quotite_et_heures_sup_rapportees_a_la_duree_legale():
    temps = TempsDuMois(
        unite="heures", reference=121.33, absences_non_payees=5.6, quotite=0.8,
        heures_sup_majorees=2.5, reference_heures_sup=151.67,
    )
    res = ratio_du_temps_paye(temps)
    assert res.ratio == round(0.8 * (121.33 - 5.6) / 121.33 + 2.5 / 151.67, 6)
    assert res.detail["quotite"] == 0.8


def test_quotites():
    from app.modules.payroll.engine.temps_travail_mois import quotite_forfait, quotite_heures

    assert quotite_heures(28) == 0.8
    assert quotite_heures(39) == 1.0
    assert quotite_forfait(None) == 1.0
    assert quotite_forfait(109) == 0.5
    assert quotite_forfait(218) == 1.0
