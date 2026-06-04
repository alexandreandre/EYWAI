"""Tests des cotisations salariales et CSG/CRDS pour les apprentis."""

from __future__ import annotations

import pytest

from app.modules.payroll.engine.calcul_cotisations import calculer_cotisations
from tests.unit.payroll.fixtures.baremes_snapshot import baremes_snapshot_csg_unifie
from tests.unit.payroll.helpers import build_test_contexte


def _total_salarial(contexte, brut):
    _, total = calculer_cotisations(contexte, brut, 0.0, 0.0)
    return round(total, 2)


def _lignes(contexte, brut):
    lignes, _ = calculer_cotisations(contexte, brut, 0.0, 0.0)
    return lignes


class TestApprentiPre2025:
    def test_exoneration_totale_sous_plafond(self):
        """Brut <= 79 % SMIC : toutes les cotisations salariales exonérées, pas de CSG."""
        b = baremes_snapshot_csg_unifie()
        ctx = build_test_contexte(
            salaire_base=1200.0,
            type_contrat="Apprentissage",
            date_debut_execution="2024-09-01",
            baremes=b,
        )
        assert _total_salarial(ctx, 1200.0) == pytest.approx(0.0, abs=0.02)
        libelles = [l["libelle"] for l in _lignes(ctx, 1200.0)]
        assert "Exonération cotisations salariales apprenti" in libelles
        # Aucune ligne CSG/CRDS (régime ancien : exonération totale)
        assert not any("CSG" in l for l in libelles)


class TestApprentiPost2025:
    def test_csg_sur_fraction_au_dela_plafond(self):
        """Brut > 50 % SMIC : CSG/CRDS sur le résiduel, abattement 1,75 %."""
        b = baremes_snapshot_csg_unifie()
        ctx = build_test_contexte(
            salaire_base=1200.0,
            type_contrat="Apprentissage",
            date_debut_execution="2025-09-01",
            baremes=b,
        )
        smic_mensuel = ctx.smic_mensuel
        plafond = round(smic_mensuel * 0.50, 2)
        residuel = round(1200.0 - plafond, 2)
        base_csg_attendue = round(residuel * (1 - 0.0175), 2)

        lignes = _lignes(ctx, 1200.0)
        csg_lignes = [l for l in lignes if "CSG" in l["libelle"]]
        assert csg_lignes, "La CSG doit s'appliquer pour un apprenti post-2025"
        for l in csg_lignes:
            assert l["base"] == pytest.approx(base_csg_attendue, abs=0.05)

        # Exonération présente et total positif mais inférieur au régime classique
        libelles = [l["libelle"] for l in lignes]
        assert "Exonération cotisations salariales apprenti" in libelles
        assert _total_salarial(ctx, 1200.0) > 0

    def test_apprenti_paie_moins_que_classique(self):
        b = baremes_snapshot_csg_unifie()
        ctx_app = build_test_contexte(
            salaire_base=1200.0,
            type_contrat="Apprentissage",
            date_debut_execution="2025-09-01",
            baremes=b,
        )
        ctx_classique = build_test_contexte(
            salaire_base=1200.0, type_contrat="CDI", baremes=b
        )
        assert _total_salarial(ctx_app, 1200.0) < _total_salarial(
            ctx_classique, 1200.0
        )


class TestApprentiMutuelleToujoursDue:
    def test_mutuelle_non_exoneree(self):
        """La mutuelle reste due même pour un apprenti (hors exonération)."""
        b = baremes_snapshot_csg_unifie()
        ctx = build_test_contexte(
            salaire_base=1200.0,
            type_contrat="Apprentissage",
            date_debut_execution="2025-09-01",
            baremes=b,
        )
        # Adhésion mutuelle ancien format (ligne forfaitaire)
        ctx.contrat["specificites_paie"]["mutuelle"] = {
            "adhesion": True,
            "lignes_specifiques": [
                {
                    "libelle": "Mutuelle",
                    "montant_salarial": 25.0,
                    "montant_patronal": 25.0,
                }
            ],
        }
        lignes = _lignes(ctx, 1200.0)
        mutuelle = [l for l in lignes if l["libelle"] == "Mutuelle"]
        assert mutuelle and mutuelle[0]["montant_salarial"] == pytest.approx(
            25.0, abs=0.01
        )
