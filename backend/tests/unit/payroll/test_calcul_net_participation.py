"""Régime paie de la participation numéraire sur un bulletin mensuel.

Participation aux bénéfices (Code du travail art. L3325-1, BOSS) :
- exonérée de cotisations sociales ;
- soumise à CSG/CRDS 9,7 % (6,8 % déductible + 2,9 % non déductible) ;
- part numéraire imposable IR (net imposable = brut − CSG déductible),
  part PEE exonérée IR.

Référence chiffrée : bulletin Cegid de M. BUGNY (participation Colorplast 2025).
"""

from __future__ import annotations

import pytest

from app.modules.payroll.engine.calcul_net import calculer_net_et_impot
from tests.unit.payroll.helpers import build_test_contexte


def _run_net(participations: list[dict] | None, *, taux_pas: float = 0.0) -> dict:
    ctx = build_test_contexte(salaire_base=2500.0, taux_pas=taux_pas)
    return calculer_net_et_impot(
        ctx,
        salaire_brut=2500.0,
        lignes_cotisations=[],
        total_cotisations_salariales=500.0,
        primes_non_soumises=[],
        remuneration_heures_supp=0.0,
        participations=participations,
    )


class TestParticipationNumeraire:
    def test_csg_97_pourcent_et_net_bugny(self):
        # Brut 3 936,59 € → CSG 6,8 % = 267,69 ; CSG 2,9 % = 114,16 ; total 381,85.
        result = _run_net(
            [
                {
                    "libelle": "Participation 2025 — numéraire",
                    "brut": 3936.59,
                    "csg_deductible": 267.69,
                    "csg_non_deductible": 114.16,
                    "csg_total": 381.85,
                }
            ]
        )
        # Salaire seul : net social 2000, net à payer 2000.
        # + participation nette numéraire = 3936.59 − 381.85 = 3554.74.
        assert result["net_a_payer"] == pytest.approx(2000.0 + 3554.74, abs=0.01)
        # Net imposable participation = brut − CSG déductible = 3668.90.
        # Salaire imposable = brut − cotis = 2500 − 500 = 2000.
        assert result["net_imposable"] == pytest.approx(2000.0 + 3668.90, abs=0.01)

    def test_acompte_deduit_du_net(self):
        result = _run_net(
            [
                {
                    "brut": 3936.59,
                    "csg_deductible": 267.69,
                    "csg_non_deductible": 114.16,
                    "csg_total": 381.85,
                    "acompte": 1000.0,
                }
            ]
        )
        # Net à payer = 2000 + (3554.74 − 1000 d'acompte déjà versé) = 4554.74.
        assert result["net_a_payer"] == pytest.approx(2000.0 + 2554.74, abs=0.01)
        # L'acompte ne réduit pas la base imposable.
        assert result["net_imposable"] == pytest.approx(2000.0 + 3668.90, abs=0.01)

    def test_part_pee_exoneree_ir_et_non_versee(self):
        # 1000 € placés sur PEE (part_pee) sur un brut de 3936.59.
        result = _run_net(
            [
                {
                    "brut": 3936.59,
                    "part_pee": 1000.0,
                    "csg_deductible": 267.69,
                    "csg_non_deductible": 114.16,
                    "csg_total": 381.85,
                }
            ]
        )
        # La part PEE n'est ni versée ni imposable : seule la part numéraire compte.
        brut_num = 3936.59 - 1000.0
        csg_ded_num = 267.69 * (brut_num / 3936.59)
        csg_tot_num = 381.85 * (brut_num / 3936.59)
        assert result["net_imposable"] == pytest.approx(
            2000.0 + (brut_num - csg_ded_num), abs=0.05
        )
        assert result["net_a_payer"] == pytest.approx(
            2000.0 + (brut_num - csg_tot_num), abs=0.05
        )

    def test_sans_participation_inchange(self):
        result = _run_net(None)
        assert result["net_a_payer"] == pytest.approx(2000.0)
        assert result["net_imposable"] == pytest.approx(2000.0)

    def test_retenue_nette_negative_appliquee(self):
        # Acompte déjà versé (−1000) + note de frais (+569,59) = −430,41 net.
        # La somme est négative : elle doit tout de même réduire le net à payer.
        ctx = build_test_contexte(salaire_base=2500.0, taux_pas=0.0)
        result = calculer_net_et_impot(
            ctx,
            salaire_brut=2500.0,
            lignes_cotisations=[],
            total_cotisations_salariales=500.0,
            primes_non_soumises=[
                {"libelle": "Acompte participation (déjà versé)", "montant": -1000.0},
                {"libelle": "Remboursement note de frais", "montant": 569.59},
            ],
            remuneration_heures_supp=0.0,
        )
        assert result["net_a_payer"] == pytest.approx(2000.0 - 430.41, abs=0.01)

    def test_pas_applique_sur_participation(self):
        # Avec un taux PAS de 10 %, l'impôt porte aussi sur la participation.
        result = _run_net(
            [
                {
                    "brut": 3936.59,
                    "csg_deductible": 267.69,
                    "csg_non_deductible": 114.16,
                    "csg_total": 381.85,
                }
            ],
            taux_pas=10.0,
        )
        net_imposable = 2000.0 + 3668.90
        pas = round(net_imposable * 0.10, 2)
        net_avant_pas = 2000.0 + 3554.74
        assert result["net_a_payer"] == pytest.approx(net_avant_pas - pas, abs=0.02)
