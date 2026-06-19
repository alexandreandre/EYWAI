"""
Scénarios de recette terrain ICCP (CDI / CDD).

Ces tests documentent les montants attendus pour validation avec la paie.
Exécuter : pytest tests/unit/payroll/test_iccp_recette_terrain.py -v
"""

from __future__ import annotations

import pytest

from app.modules.payroll.engine.iccp_arbitrage import arbitrer_iccp_complet


@pytest.mark.parametrize(
    "jours,salaire_mensuel,base_ref,expected_methode",
    [
        # CDI type : maintien gagne (salaire stable, peu de primes)
        (8, 2200.0, 26400.0, "maintien"),
        # CDI type : 1/10e gagne (fortes primes dans la base)
        (10, 1800.0, 36000.0, "dixieme"),
    ],
    ids=["cdi_maintien", "cdi_dixieme"],
)
def test_recette_cdi_arbitrage(jours, salaire_mensuel, base_ref, expected_methode):
    taux_journalier = salaire_mensuel / 21.67
    res = arbitrer_iccp_complet(
        jours,
        taux_journalier=taux_journalier,
        base_reference_dixieme=base_ref,
    )
    assert res.methode_retenue == expected_methode
    assert res.montant_final > 0


def test_recette_cdd_l1243_8_minimum():
    """CDD fin de contrat : 10 % de la rémunération totale (base déjà consolidée)."""
    from app.modules.payroll.engine.reference_remuneration import calculer_iccp_l1243_8

    base_contrat = 8800.0 + 2200.0 + 1100.0  # cumul + dernier mois + précarité
    assert calculer_iccp_l1243_8(base_contrat) == pytest.approx(1210.0, abs=0.01)
