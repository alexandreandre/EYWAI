"""Le barème de la métallurgie en données : tranches, conditions, textes.

Convention du 7 février 2022 (IDCC 3248), art. 91.1.1 à 91.1.3 (Légifrance,
02-03/11/2026). Conception du 03/11/2026. Quatre différences avec la plasturgie :
pas de carence, conditions d'ancienneté par nature (12 mois en maladie et en
trajet, 3 mois en accident du travail), ancienneté lue chaque jour, paliers
consommés sur l'année civile, plafond au net.
"""

from __future__ import annotations

import pytest

from app.modules.payroll.domain.baremes_maintien import (
    FAMILLE_ACCIDENT_TRAVAIL,
    FAMILLE_MALADIE,
    FAMILLE_PARENTALITE,
    FAMILLE_TRAJET,
    GARANTIE_PLAFOND_NET,
    METALLURGIE,
    bareme_des_reglages,
    description_lisible,
    tranche_pour,
)

pytestmark = pytest.mark.unit


def _paliers(est_cadre, mois, famille=FAMILLE_MALADIE):
    tranche = tranche_pour(METALLURGIE, est_cadre=est_cadre, mois_anciennete=mois, famille=famille)
    return None if tranche is None else [(p.taux, p.jours) for p in tranche.paliers]


@pytest.mark.parametrize(
    "mois, attendu",
    [
        (11, None),
        (12, [(1.0, 90)]),
        (59, [(1.0, 90)]),
        (60, [(1.0, 120)]),
        (119, [(1.0, 120)]),
        (120, [(1.0, 150)]),
        (179, [(1.0, 150)]),
        (180, [(1.0, 180)]),
    ],
)
def test_non_cadres_maladie(mois, attendu):
    assert _paliers(False, mois) == attendu


@pytest.mark.parametrize(
    "mois, attendu",
    [
        (11, None),
        (12, [(1.0, 90), (0.5, 90)]),
        (60, [(1.0, 120), (0.5, 120)]),
        (120, [(1.0, 150), (0.5, 150)]),
        (180, [(1.0, 180), (0.5, 180)]),
    ],
)
def test_cadres_maladie(mois, attendu):
    assert _paliers(True, mois) == attendu


def test_les_limites_sont_la_somme_des_paliers():
    assert [t.limite for t in METALLURGIE.non_cadres.tranches] == [90, 120, 150, 180]
    assert [t.limite for t in METALLURGIE.cadres.tranches] == [180, 240, 300, 360]


def test_accident_du_travail_a_trois_mois():
    # Sous 3 mois : aucun droit. À 3 mois : la tranche de l'ancienneté réelle.
    assert _paliers(False, 2, FAMILLE_ACCIDENT_TRAVAIL) is None
    assert _paliers(False, 3, FAMILLE_ACCIDENT_TRAVAIL) == [(1.0, 90)]
    assert _paliers(True, 3, FAMILLE_ACCIDENT_TRAVAIL) == [(1.0, 90), (0.5, 90)]
    # Pas de plancher de tranche pour les cadres (contrairement à la plasturgie).
    assert _paliers(True, 70, FAMILLE_ACCIDENT_TRAVAIL) == [(1.0, 120), (0.5, 120)]


def test_le_trajet_demande_un_an():
    assert _paliers(False, 11, FAMILLE_TRAJET) is None
    assert _paliers(False, 12, FAMILLE_TRAJET) == [(1.0, 90)]


def test_la_parentalite_n_est_pas_dans_le_bareme():
    assert _paliers(False, 240, FAMILLE_PARENTALITE) is None


def test_le_bareme_se_lit_dans_les_reglages():
    assert bareme_des_reglages({"bareme_convention": "metallurgie_3248"}) is METALLURGIE


def test_la_garantie_est_un_plafond_au_net():
    assert METALLURGIE.garantie == GARANTIE_PLAFOND_NET


def test_n13_la_plasturgie_n_a_aucune_condition_en_accident_du_travail():
    """Audit n° 13 (A.D. chez Colorplast) : la plasturgie ouvre l'accident du
    travail sans ancienneté ; la métallurgie demande trois mois."""
    from app.modules.payroll.domain.baremes_maintien import PLASTURGIE

    assert tranche_pour(PLASTURGIE, est_cadre=False, mois_anciennete=2,
                        famille=FAMILLE_ACCIDENT_TRAVAIL) is not None
    assert tranche_pour(METALLURGIE, est_cadre=False, mois_anciennete=2,
                        famille=FAMILLE_ACCIDENT_TRAVAIL) is None


def test_la_description_lisible_de_l_ecran():
    d = description_lisible(METALLURGIE)
    assert d["code"] == "metallurgie_3248"
    assert d["libelle"] == "Métallurgie (IDCC 3248)"
    assert [c["titre"] for c in d["categories"]] == ["Non-cadres", "Cadres"]
    assert d["categories"][0]["lignes"] == [
        {"anciennete": "1 an à moins de 5 ans", "paliers": "90 jours à 100 %", "limite": "90 jours"},
        {"anciennete": "5 ans à moins de 10 ans", "paliers": "120 jours à 100 %", "limite": "120 jours"},
        {"anciennete": "10 ans à moins de 15 ans", "paliers": "150 jours à 100 %", "limite": "150 jours"},
        {"anciennete": "15 ans et plus", "paliers": "180 jours à 100 %", "limite": "180 jours"},
    ]
    assert d["categories"][1]["lignes"][0]["paliers"] == "90 jours à 100 %, puis 90 jours à 50 %"
    assert d["categories"][0]["notes"][0] == "Pas de carence."
    assert all(s["url"].startswith("https://www.legifrance.gouv.fr/") for s in d["sources"])
