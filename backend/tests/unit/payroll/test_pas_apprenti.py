"""Tests de la base PAS et de l'exonération d'impôt annuelle des apprentis."""

from __future__ import annotations

import pytest

from app.modules.payroll.engine.calcul_net import (
    _base_pas_du_mois,
    _calculer_prelevement_a_la_source,
)
from tests.unit.payroll.helpers import build_test_contexte


def _with_cumul_net_imposable(ctx, valeur):
    ctx.cumuls = {"cumuls": {"net_imposable": valeur}}
    return ctx


class TestBasePAS:
    def test_classique_base_egale_net_imposable(self):
        ctx = build_test_contexte(type_contrat="CDI")
        assert _base_pas_du_mois(ctx, 1500.0) == pytest.approx(1500.0, abs=0.01)

    def test_apprenti_sous_smic_annuel_base_nulle(self):
        ctx = build_test_contexte(
            type_contrat="Apprentissage", date_debut_execution="2025-09-01"
        )
        _with_cumul_net_imposable(ctx, 0.0)
        # 1200 € de net imposable, loin sous le SMIC annuel -> base PAS nulle
        assert _base_pas_du_mois(ctx, 1200.0) == pytest.approx(0.0, abs=0.01)

    def test_apprenti_franchissement_smic_annuel(self):
        ctx = build_test_contexte(
            type_contrat="Apprentissage", date_debut_execution="2025-09-01"
        )
        plafond_annuel = ctx.smic_mensuel * 12  # pct 1.0
        # Cumul juste sous le plafond, le mois fait franchir
        cumul_avant = plafond_annuel - 500.0
        _with_cumul_net_imposable(ctx, cumul_avant)
        base = _base_pas_du_mois(ctx, 1200.0)
        # Fraction au-delà du plafond = (cumul_avant + 1200) - plafond = 700
        assert base == pytest.approx(700.0, abs=0.05)

    def test_apprenti_pas_nul_si_exonere(self):
        ctx = build_test_contexte(
            type_contrat="Apprentissage", date_debut_execution="2025-09-01"
        )
        ctx.contrat["specificites_paie"]["prelevement_a_la_source"]["taux"] = 10.0
        _with_cumul_net_imposable(ctx, 0.0)
        # Base PAS nulle -> impôt nul même avec un taux personnalisé
        assert _calculer_prelevement_a_la_source(ctx, 1200.0) == pytest.approx(
            0.0, abs=0.01
        )

    def test_apprenti_pas_applique_sur_base_reduite(self):
        ctx = build_test_contexte(
            type_contrat="Apprentissage", date_debut_execution="2025-09-01"
        )
        ctx.contrat["specificites_paie"]["prelevement_a_la_source"]["taux"] = 10.0
        plafond_annuel = ctx.smic_mensuel * 12
        _with_cumul_net_imposable(ctx, plafond_annuel)
        # Tout le mois est au-dessus du plafond -> base = net imposable du mois
        montant = _calculer_prelevement_a_la_source(ctx, 1200.0)
        assert montant == pytest.approx(120.0, abs=0.05)
