"""Tests de la Réduction Générale Dégressive Unique (RGDU 2026) et du garde-fou
par période (Fillon < 2026, RGDU >= 2026).

Valeurs de référence calculées à la main avec la formule officielle
(décret n°2025-887) : C = Tmin + (Tdelta × [ (1/2) × (3 × SMIC / Brut − 1) ]^P),
bornée à [Tmin, Tmin+Tdelta], nulle par discontinuité dès 3 SMIC, arrondie à 4 décimales.
"""

from __future__ import annotations

import pytest

from app.modules.payroll.engine.calcul_reduction_generale import (
    calculer_coefficient_rgdu,
    calculer_reduction_generale,
)
from tests.unit.payroll.helpers import build_test_contexte

TMIN = 0.02
TDELTA_MOINS_50 = 0.3781
TDELTA_50_PLUS = 0.3821


class TestCoefficientRgduPur:
    """Fonction pure : source unique moteur + page diagnostic."""

    def test_au_smic_coefficient_maximal(self):
        # Brut = SMIC → crochet = 1 → C = Tmin + Tdelta = Tmax.
        coef, detail = calculer_coefficient_rgdu(
            1800.0, 1800.0, tmin=TMIN, tdelta=TDELTA_MOINS_50, p=1.75
        )
        assert coef == pytest.approx(0.3981, abs=1e-4)
        assert detail["tmax"] == pytest.approx(0.3981, abs=1e-4)
        assert detail["plafond_applique"] is False

    def test_au_smic_effectif_50_et_plus(self):
        coef, _ = calculer_coefficient_rgdu(
            1800.0, 1800.0, tmin=TMIN, tdelta=TDELTA_50_PLUS, p=1.75
        )
        assert coef == pytest.approx(0.4021, abs=1e-4)

    def test_a_deux_smic_valeur_intermediaire(self):
        # Brut = 2 SMIC → crochet = 0.25 → 0.25^1.75 ≈ 0.088388.
        coef, _ = calculer_coefficient_rgdu(
            3600.0, 1800.0, tmin=TMIN, tdelta=TDELTA_MOINS_50, p=1.75
        )
        assert coef == pytest.approx(0.0534, abs=1e-4)

    def test_juste_sous_trois_smic_plancher_tmin(self):
        # Brut = 2,99 SMIC → le coefficient s'approche du plancher Tmin (pas 0).
        coef, _ = calculer_coefficient_rgdu(
            2.99 * 1800.0, 1800.0, tmin=TMIN, tdelta=TDELTA_MOINS_50, p=1.75
        )
        assert coef == pytest.approx(TMIN, abs=1e-4)
        assert coef > 0.0

    def test_a_trois_smic_discontinuite_nul(self):
        # À exactement 3 SMIC : nul par discontinuité (et non Tmin).
        coef, detail = calculer_coefficient_rgdu(
            5400.0, 1800.0, tmin=TMIN, tdelta=TDELTA_MOINS_50, p=1.75
        )
        assert coef == 0.0
        assert "discontinuité" in detail["resultat"]

    def test_au_dela_trois_smic_nul(self):
        coef, _ = calculer_coefficient_rgdu(
            6000.0, 1800.0, tmin=TMIN, tdelta=TDELTA_MOINS_50, p=1.75
        )
        assert coef == 0.0

    def test_arrondi_quatre_decimales(self):
        coef, _ = calculer_coefficient_rgdu(
            2500.0, 1800.0, tmin=TMIN, tdelta=TDELTA_MOINS_50, p=1.75
        )
        # 4 décimales max.
        assert round(coef, 4) == coef

    def test_brut_nul_renvoie_zero(self):
        coef, _ = calculer_coefficient_rgdu(
            0.0, 1800.0, tmin=TMIN, tdelta=TDELTA_MOINS_50, p=1.75
        )
        assert coef == 0.0


class TestReductionGeneraleGardeFou:
    """Aiguillage Fillon (< 2026) / RGDU (>= 2026) via contexte.year."""

    def test_rgdu_2026_montant(self):
        ctx = build_test_contexte(salaire_base=2000.0, effectif=10)
        ctx.year = 2026
        heures = 151.67  # (35 × 52) / 12
        red = calculer_reduction_generale(ctx, 2000.0, heures)
        assert red is not None
        # SMIC ref = 12.31 × 151.67 ≈ 1867.06 ; C ≈ 0.3346 ; réduction ≈ 669.2.
        assert red["taux_patronal"] == pytest.approx(0.3346, abs=2e-3)
        assert red["montant_patronal"] == pytest.approx(-669.2, abs=2.0)
        assert red["valeur_cumulative_a_enregistrer"] == pytest.approx(669.2, abs=2.0)

    def test_garde_fou_2025_vs_2026_differents(self):
        ctx_2025 = build_test_contexte(salaire_base=2000.0, effectif=10)
        ctx_2025.year = 2025
        ctx_2026 = build_test_contexte(salaire_base=2000.0, effectif=10)
        ctx_2026.year = 2026
        red_2025 = calculer_reduction_generale(ctx_2025, 2000.0, 151.67)
        red_2026 = calculer_reduction_generale(ctx_2026, 2000.0, 151.67)
        # Fillon 2025 : réduction très faible (T quasi nul dans le snapshot).
        assert abs(red_2025["montant_patronal"]) < 50.0
        # RGDU 2026 : réduction nettement plus importante.
        assert red_2026["montant_patronal"] < -500.0
        assert red_2025["montant_patronal"] != red_2026["montant_patronal"]

    def test_effectif_change_tdelta(self):
        ctx_petit = build_test_contexte(salaire_base=1900.0, effectif=10)
        ctx_petit.year = 2026
        ctx_grand = build_test_contexte(salaire_base=1900.0, effectif=80)
        ctx_grand.year = 2026
        red_petit = calculer_reduction_generale(ctx_petit, 1900.0, 151.67)
        red_grand = calculer_reduction_generale(ctx_grand, 1900.0, 151.67)
        # FNAL >= 50 → Tdelta plus élevé → coefficient (légèrement) plus élevé.
        assert red_grand["taux_patronal"] > red_petit["taux_patronal"]

    def test_toggle_actif_false_pas_de_reduction(self):
        ctx = build_test_contexte(salaire_base=2000.0, effectif=10)
        ctx.year = 2026
        ctx.baremes["reduction_generale"]["actif"] = False
        red = calculer_reduction_generale(ctx, 2000.0, 151.67)
        # Cumuls vides → aucune réduction à rembourser → pas de ligne.
        assert red is None

    def test_toggle_actif_false_rembourse_cumul(self):
        ctx = build_test_contexte(salaire_base=2000.0, effectif=10)
        ctx.year = 2026
        ctx.baremes["reduction_generale"]["actif"] = False
        ctx.cumuls = {"cumuls": {"reduction_generale_patronale": -120.0}}
        red = calculer_reduction_generale(ctx, 2000.0, 151.67)
        assert red is not None
        # Remboursement positif du cumul déjà appliqué.
        assert red["montant_patronal"] == pytest.approx(120.0, abs=0.01)
        assert red["valeur_cumulative_a_enregistrer"] == 0.0

    def test_config_absente_renvoie_none(self):
        ctx = build_test_contexte(salaire_base=2000.0, effectif=10)
        ctx.year = 2026
        ctx.baremes["reduction_generale"] = {}
        red = calculer_reduction_generale(ctx, 2000.0, 151.67)
        assert red is None

    def test_regularisation_progressive_differentiel(self):
        # Mois 2 : la réduction du mois = total dû cumulé − déjà appliqué.
        ctx = build_test_contexte(salaire_base=2000.0, effectif=10)
        ctx.year = 2026
        ctx.cumuls = {
            "cumuls": {
                "brut_total": 2000.0,
                "heures_remunerees": 151.67,
                "reduction_generale_patronale": -669.2,
            }
        }
        red = calculer_reduction_generale(ctx, 2000.0, 151.67)
        assert red is not None
        # Salaire stable → la réduction du mois ≈ celle du mois 1.
        assert red["montant_patronal"] == pytest.approx(-669.2, abs=2.0)
        # Le cumul enregistré double (2 mois).
        assert red["valeur_cumulative_a_enregistrer"] == pytest.approx(1338.4, abs=4.0)
