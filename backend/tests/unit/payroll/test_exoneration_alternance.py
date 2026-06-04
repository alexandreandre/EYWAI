"""Tests du module pur d'exonération des alternants (sans réseau)."""

from __future__ import annotations

import pytest

from app.modules.payroll.engine.exoneration_alternance import (
    assiette_residuelle,
    contexte_exoneration_apprenti,
    plafond_exoneration_apprenti,
    selectionner_regime_apprenti,
)
from tests.unit.payroll.helpers import build_test_contexte


def _smic_mensuel_plein(ctx) -> float:
    return ctx.smic_mensuel


class TestSelectionRegime:
    def test_non_apprenti_renvoie_none(self):
        ctx = build_test_contexte(type_contrat="CDI")
        assert contexte_exoneration_apprenti(ctx) is None

    def test_regime_post_2025_par_date_execution(self):
        ctx = build_test_contexte(
            type_contrat="Apprentissage",
            date_debut_execution="2025-09-01",
        )
        regime = selectionner_regime_apprenti(ctx)
        assert regime["plafond_exoneration_pct_smic"] == 0.50
        assert regime["csg_crds_assujettie_au_dela_plafond"] is True

    def test_regime_pre_2025_par_date_execution(self):
        ctx = build_test_contexte(
            type_contrat="Apprentissage",
            date_debut_execution="2024-10-01",
        )
        regime = selectionner_regime_apprenti(ctx)
        assert regime["plafond_exoneration_pct_smic"] == 0.79
        assert regime["csg_crds_assujettie_au_dela_plafond"] is False

    def test_flag_maintien_conserve_ancien_regime(self):
        # Contrat conclu avant la bascule, exécuté après : maintien possible.
        ctx = build_test_contexte(
            type_contrat="Apprentissage",
            date_conclusion_contrat="2025-02-15",
            date_debut_execution="2025-04-01",
            maintien_regime_apprenti=True,
        )
        regime = selectionner_regime_apprenti(ctx)
        assert regime["plafond_exoneration_pct_smic"] == 0.79

    def test_sans_flag_maintien_bascule_au_nouveau_regime(self):
        ctx = build_test_contexte(
            type_contrat="Apprentissage",
            date_conclusion_contrat="2025-02-15",
            date_debut_execution="2025-04-01",
            maintien_regime_apprenti=False,
        )
        regime = selectionner_regime_apprenti(ctx)
        assert regime["plafond_exoneration_pct_smic"] == 0.50

    def test_fallback_date_entree_si_execution_absente(self):
        # date_entree 2020 -> régime pré-2025
        ctx = build_test_contexte(type_contrat="Apprentissage")
        regime = selectionner_regime_apprenti(ctx)
        assert regime["plafond_exoneration_pct_smic"] == 0.79


class TestPlafondEtAssiette:
    def test_plafond_temps_plein_post_2025(self):
        ctx = build_test_contexte(
            type_contrat="Apprentissage",
            date_debut_execution="2025-09-01",
            duree_hebdo=35.0,
        )
        regime = selectionner_regime_apprenti(ctx)
        attendu = round(ctx.smic_mensuel * 0.50, 2)
        assert plafond_exoneration_apprenti(ctx, regime) == pytest.approx(
            attendu, abs=0.01
        )

    def test_plafond_proratise_temps_partiel(self):
        ctx = build_test_contexte(
            type_contrat="Apprentissage",
            date_debut_execution="2025-09-01",
            duree_hebdo=28.0,
        )
        regime = selectionner_regime_apprenti(ctx)
        plafond = plafond_exoneration_apprenti(ctx, regime)
        attendu = round(ctx.smic_mensuel * (28.0 / 35.0) * 0.50, 2)
        assert plafond == pytest.approx(attendu, abs=0.01)

    def test_assiette_residuelle(self):
        assert assiette_residuelle(1200.0, 901.0) == pytest.approx(299.0, abs=0.01)
        assert assiette_residuelle(800.0, 901.0) == 0.0


class TestContexteExoneration:
    def test_contexte_complet_post_2025(self):
        ctx = build_test_contexte(
            type_contrat="Apprentissage",
            date_debut_execution="2025-09-01",
        )
        exo = contexte_exoneration_apprenti(ctx)
        assert exo is not None
        assert exo["csg_crds_assujettie"] is True
        assert exo["abattement_csg"] == pytest.approx(0.0175, abs=1e-6)
        assert "mutuelle" in exo["cotisations_exclues"]
        assert "apec" in exo["cotisations_exclues"]
        assert exo["exoneration_ir"]["actif"] is True
