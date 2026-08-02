"""Tests indemnité transport contractuelle vs remboursement abonnement 50 %."""

from __future__ import annotations

import pytest

from app.modules.payroll.engine.calcul_net import calculer_net_et_impot
from tests.unit.payroll.helpers import build_test_contexte


def _run_net(transport: dict | None) -> dict:
    ctx = build_test_contexte(
        salaire_base=2500.0,
        taux_pas=0.0,
        specificites_extra={"transport": transport or {}},
    )
    return calculer_net_et_impot(
        ctx,
        salaire_brut=2500.0,
        lignes_cotisations=[],
        total_cotisations_salariales=500.0,
        primes_non_soumises=[],
        remuneration_heures_supp=0.0,
    )


class TestCalculNetTransport:
    def test_abonnement_seul_50_pourcent(self):
        result = _run_net({"abonnement_mensuel_total": 120.0})
        assert result["remboursement_transport"] == pytest.approx(60.0)
        assert result["indemnite_transport_fixe"] == pytest.approx(0.0)
        assert result["net_a_payer"] == pytest.approx(2000.0 + 60.0)

    def test_indemnite_contractuelle_nest_plus_ajoutee_par_le_moteur(self):
        """L'indemnité trajet domicile-travail passe désormais par une saisie
        mensuelle générée (règle transport_domicile_travail de payroll_variables),
        pour être visible et corrigeable dans Saisies > Primes, proratisée à
        l'entrée/sortie et retirée en cas d'absence sur tout le mois.

        La conserver ici la compterait deux fois."""
        result = _run_net({"indemnite_mensuelle_nette": 75.0})
        assert result["remboursement_transport"] == pytest.approx(0.0)
        assert result["indemnite_transport_fixe"] == pytest.approx(0.0)
        assert result["net_a_payer"] == pytest.approx(2000.0)

    def test_abonnement_reste_intact_quand_une_indemnite_coexiste(self):
        """Le remboursement 50 % de l'abonnement est une obligation légale
        distincte : il reste porté par le moteur."""
        result = _run_net(
            {
                "abonnement_mensuel_total": 120.0,
                "indemnite_mensuelle_nette": 75.0,
            }
        )
        assert result["remboursement_transport"] == pytest.approx(60.0)
        assert result["indemnite_transport_fixe"] == pytest.approx(0.0)
        assert result["net_a_payer"] == pytest.approx(2000.0 + 60.0)

    def test_sans_transport_inchange(self):
        result = _run_net({})
        assert result["remboursement_transport"] == pytest.approx(0.0)
        assert result["indemnite_transport_fixe"] == pytest.approx(0.0)
        assert result["net_a_payer"] == pytest.approx(2000.0)
