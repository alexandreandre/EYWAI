"""Le SMIC horaire suit la période du bulletin.

Le barème du SMIC n'avait aucune notion de date : une seule valeur active, celle
d'aujourd'hui, servait à tous les mois. Un bulletin de janvier 2026 refabriqué
affichait donc le SMIC de septembre.

Le cabinet, lui, imprime bien celui de la période. Sur les bulletins Colorplast
de 2026 : 12,02 € de janvier à mai, 12,31 € à partir de juin.

Ce n'est pas qu'une question d'affichage. Le SMIC plafonne l'exonération de
cotisations des apprentis (`smic_mensuel_proratise`) : une valeur trop haute sur
un mois passé relève leur plafond et change leurs cotisations. Colorplast n'a pas
d'apprenti, d'autres sociétés du groupe si.

Le barème peut désormais porter un `historique` : une liste de valeurs avec leur
date d'entrée en vigueur, la plus récente qui précède la fin de la période
l'emportant. Sans historique, la valeur unique s'applique comme avant — aucun
bulletin existant ne bouge.
"""

from __future__ import annotations

import copy
from datetime import date

import pytest

from .fixtures.baremes_snapshot import baremes_snapshot
from .helpers import build_test_contexte

pytestmark = pytest.mark.unit

#: Ce que le cabinet imprime sur les bulletins Colorplast de 2026.
HISTORIQUE_2026 = [
    {"date_debut": "2026-01-01", "cas_general": 12.02},
    {"date_debut": "2026-06-01", "cas_general": 12.31},
]


def _contexte(fin_periode: date | None, avec_historique=True):
    b = copy.deepcopy(baremes_snapshot())
    b.setdefault("smic", {})["cas_general"] = 12.31
    if avec_historique:
        b["smic"]["historique"] = HISTORIQUE_2026
    ctx = build_test_contexte(baremes=b)
    ctx.date_fin_periode = fin_periode
    return ctx


class TestSmicHistorise:
    @pytest.mark.parametrize(
        "fin_periode, attendu",
        [
            (date(2026, 1, 31), 12.02),
            (date(2026, 5, 31), 12.02),
            (date(2026, 6, 30), 12.31),
            (date(2026, 7, 31), 12.31),
            (date(2026, 9, 30), 12.31),
        ],
    )
    def test_la_valeur_suit_le_mois(self, fin_periode, attendu):
        assert _contexte(fin_periode).smic_horaire == pytest.approx(attendu, abs=0.001)

    def test_sans_historique_la_valeur_unique_s_applique(self):
        """Garde anti-régression : aucun bulletin existant ne bouge."""
        ctx = _contexte(date(2026, 1, 31), avec_historique=False)
        assert ctx.smic_horaire == pytest.approx(12.31, abs=0.001)

    def test_sans_periode_connue_on_prend_la_valeur_courante(self):
        assert _contexte(None).smic_horaire == pytest.approx(12.31, abs=0.001)

    def test_periode_anterieure_a_tout_l_historique(self):
        """Un mois plus ancien que la première date connue retombe sur la
        valeur unique plutôt que d'inventer un SMIC."""
        assert _contexte(date(2025, 3, 31)).smic_horaire == pytest.approx(12.31, abs=0.001)

    def test_le_smic_mensuel_suit_aussi(self):
        ctx = _contexte(date(2026, 1, 31))
        assert ctx.smic_mensuel == pytest.approx(12.02 * 35 * 52 / 12, abs=0.01)
