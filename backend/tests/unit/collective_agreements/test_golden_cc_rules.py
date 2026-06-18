"""Tests golden paie avec règles CC prioritaires."""

from __future__ import annotations

from copy import deepcopy
from datetime import date

import pytest

from app.modules.payroll.engine.calcul_brut import calculer_salaire_brut
from tests.unit.collective_agreements.fixtures.cc_rules_snapshot import (
    PRIORITY_IDCC_RULES,
    conventions_collectives_snapshot,
)
from tests.unit.payroll.helpers import build_test_contexte, _weekday_calendrier


def _contexte_avec_idcc(idcc: str, coefficient: float | None = None):
    baremes = deepcopy(
        __import__(
            "tests.unit.payroll.fixtures.baremes_snapshot",
            fromlist=["baremes_snapshot"],
        ).baremes_snapshot()
    )
    baremes["conventions_collectives"] = conventions_collectives_snapshot()
    ctx = build_test_contexte(salaire_base=3000.0, baremes=baremes)
    ctx.contrat["remuneration"]["convention_collective"] = {"idcc": idcc}
    if coefficient is not None:
        ctx.contrat["remuneration"]["classification_conventionnelle"] = {
            "coefficient": coefficient
        }
    return ctx


class TestGoldenCCRules:
    @pytest.mark.parametrize(
        "idcc,coefficient,expected_prime_gain",
        [
            ("1486", 240, 100.0),  # 2500 * 0.04 (6 ans, palier 5 ans)
            ("1090", 150, 120.0),  # 3000 * 0.04 (6 ans, palier 6 ans → 0.04)
            ("0044", None, 90.0),  # 3000 * 0.03 (6 ans, palier 5 ans)
            ("0292", None, 144.0),  # 3000 * 0.048 (6 ans, palier plasturgie)
            ("1297", None, 144.0),  # alias plasturgie dans certains jeux de données
        ],
    )
    def test_prime_anciennete_par_idcc(
        self, idcc: str, coefficient: float | None, expected_prime_gain: float
    ):
        ctx = _contexte_avec_idcc(idcc, coefficient)
        year, month = 2026, 4
        cal = _weekday_calendrier(year, month)
        result = calculer_salaire_brut(
            ctx,
            calendrier_saisie=cal,
            date_debut_periode=date(year, month, 1),
            date_fin_periode=date(year, month, 28),
            primes_saisies=[],
        )
        lignes = result.get("lignes_composants_brut", [])
        prime_lignes = [l for l in lignes if "ancienneté" in l.get("libelle", "").lower()]
        assert len(prime_lignes) == 1
        assert prime_lignes[0]["gain"] == pytest.approx(expected_prime_gain, abs=0.02)

    def test_syntec_sans_coefficient_pas_de_prime_sur_minima(self):
        """Sans coefficient, base minima = 0 → pas de prime si methode minima CC."""
        ctx = _contexte_avec_idcc("1486", coefficient=None)
        year, month = 2026, 4
        cal = _weekday_calendrier(year, month)
        result = calculer_salaire_brut(
            ctx,
            calendrier_saisie=cal,
            date_debut_periode=date(year, month, 1),
            date_fin_periode=date(year, month, 28),
            primes_saisies=[],
        )
        lignes = result.get("lignes_composants_brut", [])
        prime_lignes = [l for l in lignes if "ancienneté" in l.get("libelle", "").lower()]
        assert len(prime_lignes) == 0

    @pytest.mark.parametrize("idcc", list(PRIORITY_IDCC_RULES.keys()))
    def test_fixture_chargee_dans_baremes(self, idcc: str):
        ctx = _contexte_avec_idcc(idcc)
        rules = ctx.baremes["conventions_collectives"].get(f"idcc_{idcc}")
        assert rules is not None
        assert rules["idcc"] == idcc
