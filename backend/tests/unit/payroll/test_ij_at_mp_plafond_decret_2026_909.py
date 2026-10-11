"""IJ d'accident du travail et de maladie professionnelle : plafond daté.

Règle (CSS R433-2, modifié par le décret n° 2026-909 du 30/09/2026, JORF
n° 0229 du 01/10/2026, art. 1er 2° et art. 3 :
https://www.legifrance.gouv.fr/eli/decret/2026/9/30/SFHS2621736D/jo/texte ;
Service Public, actualité A19080 du 08/10/2026 :
https://www.service-public.gouv.fr/particuliers/actualites/A19080) : le
salaire journalier de base des IJ AT/MP est retenu dans la limite de
0,226 % du plafond annuel de la Sécurité sociale (« soit l'équivalent de
1,8 fois le Smic ») pour les arrêts qui surviennent à compter du 01/11/2026,
contre 0,834 % auparavant. Un arrêt commencé avant le 01/11/2026 garde
l'ancien plafond, même s'il se poursuit après. Le complément employeur suit
(maintien − IJ) : « une hausse du complément de salaire à la charge de
l'employeur, lorsqu'un maintien de salaire est applicable ».

Le moteur plafonnait le salaire journalier AT/MP à 1,8 plafond de la
Sécurité sociale journalier (237,01 € en 2026), quelle que soit la date.
"""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest

from app.modules.payroll.engine.maintien_salaire_service import calculer_maintien

pytestmark = pytest.mark.unit

PASS_2026 = 48060.0
ANCIEN_PLAFOND = 0.00834 * PASS_2026  # 400,82 €/jour
NOUVEAU_PLAFOND = 0.00226 * PASS_2026  # 108,62 €/jour


def _ctx(salaire_base: float) -> SimpleNamespace:
    return SimpleNamespace(
        salaire_base_mensuel=salaire_base,
        statut_salarie="Non-Cadre",
        baremes={
            "pss": {"annuel": PASS_2026},
            "ij_plafonds": {
                "maladie": 42.97,
                "maternite_paternite": 104.02,
                "at_mp": 240.49,
                "at_mp_majoree": 320.66,
            },
        },
        contrat={"contrat": {"date_entree": "2020-01-06", "statut": "Non-Cadre"}},
    )


def _arret(arret_type: str, debut: str, fin: str, subrogation: bool = False) -> dict:
    return {
        "arret_type": arret_type,
        "date_debut": debut,
        "date_fin": fin,
        "subrogation_active": subrogation,
        "nombre_enfants": 0,
        "salaire_periode_reelle": 0.0,
    }


REGLAGE = {"apply_legal_maintenance": True, "min_seniority_months": 12}
NOVEMBRE = (date(2026, 11, 1), date(2026, 11, 30))


def _calcul(arret, salaire_base, periode=NOVEMBRE):
    return calculer_maintien(arret, _ctx(salaire_base), REGLAGE, *periode)


@pytest.mark.parametrize(
    "arret_type", ["accident_travail", "maladie_professionnelle", "accident_trajet", "rechute_at"]
)
def test_arret_at_mp_du_1er_novembre_2026_plafonne_a_0_226_pct_du_pass(arret_type):
    ijss = _calcul(_arret(arret_type, "2026-11-01", "2026-11-30"), 5000.0)["ijss"]
    assert ijss["salaire_journalier_base"] == pytest.approx(5000.0 / 30.42, abs=0.0001)
    assert ijss["base_plafonnee"] == pytest.approx(NOUVEAU_PLAFOND, abs=0.0001)
    # 60 % jusqu'au 28e jour, 80 % ensuite (29 et 30 novembre).
    attendu = 28 * 0.6 * NOUVEAU_PLAFOND + 2 * 0.8 * NOUVEAU_PLAFOND
    assert ijss["ijss_theorique"] == pytest.approx(round(attendu, 2), abs=0.01)


def test_au_dela_du_28e_jour_80_pct_du_nouveau_plafond():
    # Arrêt du 02/11 : décembre entier au-delà du 29e jour.
    ijss = _calcul(
        _arret("accident_travail", "2026-11-02", "2026-12-31"),
        5000.0,
        (date(2026, 12, 1), date(2026, 12, 31)),
    )["ijss"]
    assert ijss["ijss_journaliere"] == pytest.approx(0.8 * NOUVEAU_PLAFOND, abs=0.0001)
    assert ijss["ijss_journaliere"] == pytest.approx(86.89, abs=0.005)


def test_arret_commence_en_octobre_garde_l_ancien_plafond_en_novembre():
    # Salaire journalier de 164,37 € : sous l'ancien plafond (400,82 €),
    # au-dessus du nouveau (108,62 €). L'arrêt du 20/10 garde l'ancien.
    ijss = _calcul(_arret("accident_travail", "2026-10-20", "2026-11-30"), 5000.0)["ijss"]
    sjb = 5000.0 / 30.42
    assert ijss["base_plafonnee"] == pytest.approx(sjb, abs=0.0001)
    # Novembre : 1er au 16 = 13e au 28e jour (60 %), 17 au 30 (80 %).
    attendu = 16 * 0.6 * sjb + 14 * 0.8 * sjb
    assert ijss["ijss_theorique"] == pytest.approx(round(attendu, 2), abs=0.01)


def test_l_ancien_plafond_est_0_834_pct_du_pass():
    # Salaire de 10 000 € : 328,73 €/jour, sous 0,834 % du PASS (400,82 €),
    # au-dessus de 1,8 plafond journalier (237,01 €).
    ijss = _calcul(
        _arret("accident_travail", "2026-10-05", "2026-10-31"),
        10000.0,
        (date(2026, 10, 1), date(2026, 10, 31)),
    )["ijss"]
    assert ijss["base_plafonnee"] == pytest.approx(10000.0 / 30.42, abs=0.0001)
    ijss = _calcul(
        _arret("accident_travail", "2026-10-05", "2026-10-31"),
        13000.0,
        (date(2026, 10, 1), date(2026, 10, 31)),
    )["ijss"]
    assert ijss["base_plafonnee"] == pytest.approx(ANCIEN_PLAFOND, abs=0.0001)


def test_la_maladie_n_est_pas_touchee():
    # La maladie garde son plafond de 1,4 Smic (barème Smic absent : repli
    # historique), sans le plafond AT/MP.
    ijss = _calcul(_arret("maladie_simple", "2026-11-02", "2026-11-30"), 2000.0)["ijss"]
    assert ijss["base_plafonnee"] == pytest.approx(2000.0 * 3 / 91.25, abs=0.0001)


def test_le_complement_employeur_suit_les_ij_plafonnees():
    res = _calcul(_arret("accident_travail", "2026-11-02", "2026-11-30", subrogation=True), 5000.0)
    ijss, maintien = res["ijss"], res["maintien"]
    # 29 jours : 28 à 60 % du nouveau plafond, le 29e (30/11) à 80 %.
    attendu = 28 * 0.6 * NOUVEAU_PLAFOND + 0.8 * NOUVEAU_PLAFOND
    assert ijss["ijss_theorique"] == pytest.approx(round(attendu, 2), abs=0.01)
    assert maintien["maintien_verse"] == pytest.approx(
        round(maintien["maintien_cible"] - ijss["ijss_theorique"], 2), abs=0.01
    )
    # Maintien à 90 % du salaire journalier (5 000 ÷ 30,42) sur 29 jours.
    assert maintien["maintien_cible"] == pytest.approx(round(29 * 0.9 * 5000.0 / 30.42, 2), abs=0.01)
