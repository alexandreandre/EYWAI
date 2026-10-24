"""Le barème de la plasturgie en données : tranches, paliers, limites, textes.

Avenant non-cadres du 15/05/1991, art. 13 ; accord cadres du 17/12/1992, art. 5
(Légifrance, 24/10/2026). Conception du 24/10/2026.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.modules.payroll.domain.baremes_maintien import (
    FAMILLE_ACCIDENT_TRAVAIL,
    FAMILLE_MALADIE,
    FAMILLE_PARENTALITE,
    FAMILLE_TRAJET,
    PLASTURGIE,
    bareme_des_reglages,
    description_lisible,
    famille_du_type,
    mois_complets,
    pourcent,
    tranche_pour,
)

pytestmark = pytest.mark.unit


def _paliers(est_cadre, mois, famille=FAMILLE_MALADIE):
    tranche = tranche_pour(PLASTURGIE, est_cadre=est_cadre, mois_anciennete=mois, famille=famille)
    return None if tranche is None else [(p.taux, p.jours) for p in tranche.paliers]


@pytest.mark.parametrize(
    "mois, attendu",
    [
        (11, None),
        (12, [(1.0, 45), (0.75, 60)]),
        (59, [(1.0, 45), (0.75, 60)]),
        (60, [(1.0, 60), (0.75, 75)]),
        (274, [(1.0, 60), (0.75, 75)]),
    ],
)
def test_non_cadres_maladie(mois, attendu):
    assert _paliers(False, mois) == attendu


@pytest.mark.parametrize(
    "mois, attendu",
    [
        (11, None),
        (12, [(1.0, 45), (0.5, 45)]),
        (24, [(1.0, 60), (0.5, 60)]),
        (36, [(1.0, 90), (0.5, 90)]),
        (60, [(1.0, 120), (0.5, 120)]),
        (119, [(1.0, 120), (0.5, 120)]),
        (120, [(1.0, 150), (0.5, 150)]),
    ],
)
def test_cadres_maladie(mois, attendu):
    assert _paliers(True, mois) == attendu


def test_les_limites_sont_la_somme_des_paliers():
    assert [t.limite for t in PLASTURGIE.non_cadres.tranches] == [105, 135]
    assert [t.limite for t in PLASTURGIE.cadres.tranches] == [90, 120, 180, 240, 300]


def test_accident_du_travail_sans_condition_d_anciennete():
    assert _paliers(False, 6, FAMILLE_ACCIDENT_TRAVAIL) == [(1.0, 45), (0.75, 60)]
    # Cadres : au moins la tranche de 2 ans, hors trajet.
    assert _paliers(True, 6, FAMILLE_ACCIDENT_TRAVAIL) == [(1.0, 60), (0.5, 60)]
    assert _paliers(True, 40, FAMILLE_ACCIDENT_TRAVAIL) == [(1.0, 90), (0.5, 90)]
    assert _paliers(True, 6, FAMILLE_TRAJET) == [(1.0, 45), (0.5, 45)]
    assert _paliers(False, 6, FAMILLE_TRAJET) == [(1.0, 45), (0.75, 60)]


def test_la_parentalite_n_est_pas_dans_le_bareme():
    assert _paliers(False, 120, FAMILLE_PARENTALITE) is None


def test_le_taux_du_rang():
    tranche = tranche_pour(PLASTURGIE, est_cadre=False, mois_anciennete=60, famille=FAMILLE_MALADIE)
    assert [tranche.taux_du_rang(r) for r in (1, 60, 61, 135, 136)] == [1.0, 1.0, 0.75, 0.75, 0.0]


@pytest.mark.parametrize(
    "type_arret, famille",
    [
        ("maladie_simple", FAMILLE_MALADIE),
        ("maladie", FAMILLE_MALADIE),
        ("ald", FAMILLE_MALADIE),
        ("mi_temps_therapeutique", FAMILLE_MALADIE),
        ("accident_travail", FAMILLE_ACCIDENT_TRAVAIL),
        ("maladie_professionnelle", FAMILLE_ACCIDENT_TRAVAIL),
        ("rechute_at", FAMILLE_ACCIDENT_TRAVAIL),
        ("accident_trajet", FAMILLE_TRAJET),
        ("maternite", FAMILLE_PARENTALITE),
        ("paternite_accueil_enfant", FAMILLE_PARENTALITE),
    ],
)
def test_famille_du_type(type_arret, famille):
    assert famille_du_type(type_arret) == famille


def test_mois_complets_a_l_anniversaire():
    # Entrée le 28/05/2025 : 11 mois le 05/05/2026, 12 le 28/05/2026.
    assert mois_complets(date(2025, 5, 28), date(2026, 5, 5)) == 11
    assert mois_complets(date(2025, 5, 28), date(2026, 5, 28)) == 12
    assert mois_complets(date(2003, 7, 15), date(2026, 5, 4)) == 273


def test_le_bareme_se_lit_dans_les_reglages():
    assert bareme_des_reglages({"bareme_convention": "plasturgie_0292"}) is PLASTURGIE
    assert bareme_des_reglages({"bareme_convention": None}) is None
    assert bareme_des_reglages({}) is None
    assert bareme_des_reglages({"bareme_convention": "inconnu"}) is None


def test_pourcent():
    assert [pourcent(t) for t in (1.0, 0.75, 0.5, 0.9, 2 / 3)] == [
        "100 %", "75 %", "50 %", "90 %", "66,67 %",
    ]


def test_la_description_lisible_de_l_ecran():
    d = description_lisible(PLASTURGIE)
    assert d["code"] == "plasturgie_0292"
    assert d["libelle"] == "Plasturgie (IDCC 0292)"
    assert [c["titre"] for c in d["categories"]] == ["Non-cadres", "Cadres"]
    assert d["categories"][0]["lignes"] == [
        {"anciennete": "1 an à moins de 5 ans",
         "paliers": "45 jours à 100 %, puis 60 jours à 75 %", "limite": "105 jours"},
        {"anciennete": "5 ans et plus",
         "paliers": "60 jours à 100 %, puis 75 jours à 75 %", "limite": "135 jours"},
    ]
    assert [l["anciennete"] for l in d["categories"][1]["lignes"]] == [
        "1 an à moins de 2 ans", "2 ans à moins de 3 ans", "3 ans à moins de 5 ans",
        "5 ans à moins de 10 ans", "10 ans et plus",
    ]
    assert d["categories"][1]["lignes"][-1]["paliers"] == "150 jours à 100 %, puis 150 jours à 50 %"
    assert d["categories"][1]["notes"][0] == "Pas de carence."
    assert all(s["url"].startswith("https://www.legifrance.gouv.fr/") for s in d["sources"])
    assert "Chaque mois, Martine compare avec le maintien légal et verse le plus favorable." in d["regles"]
