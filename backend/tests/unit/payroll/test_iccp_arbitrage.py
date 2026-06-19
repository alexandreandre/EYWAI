"""Tests unitaires — arbitrage ICCP maintien / 1/10e."""

from __future__ import annotations

import pytest

from app.modules.payroll.engine.iccp_arbitrage import (
    arbitrer_iccp,
    arbitrer_iccp_complet,
    calculer_dixieme,
    calculer_maintien_horaire,
    calculer_maintien_journalier,
)


def test_maintien_journalier_basique():
    assert calculer_maintien_journalier(8, 101.56) == pytest.approx(812.48, abs=0.02)


def test_dixieme_basique():
    montant, valeur_jour = calculer_dixieme(8, 26400.0)
    assert valeur_jour == pytest.approx(88.0, abs=0.01)
    assert montant == pytest.approx(704.0, abs=0.02)


def test_arbitrage_maintien_gagne():
    res = arbitrer_iccp(8, 812.45, 704.0, taux_journalier=101.56, base_reference_dixieme=26400.0)
    assert res.methode_retenue == "maintien"
    assert res.montant_final == 812.45


def test_arbitrage_dixieme_gagne():
    res = arbitrer_iccp(8, 600.0, 704.0, base_reference_dixieme=26400.0)
    assert res.methode_retenue == "dixieme"
    assert res.montant_final == 704.0


def test_arbitrage_egalite_retenu_maintien():
    res = arbitrer_iccp(5, 500.0, 500.0)
    assert res.methode_retenue == "maintien"
    assert res.montant_final == 500.0


def test_zero_jours():
    res = arbitrer_iccp_complet(0, taux_journalier=100.0, base_reference_dixieme=20000.0)
    assert res.montant_final == 0.0


def test_maintien_horaire_avec_hs():
    detail = calculer_maintien_horaire(
        5,
        15.0,
        heures_normales_par_jour=7.0,
        heures_supp_par_jour=0.8,
        majoration_hs=0.25,
    )
    assert detail.total > 5 * 7 * 15.0
    res = arbitrer_iccp_complet(
        5,
        maintien_horaire=detail,
        base_reference_dixieme=18000.0,
    )
    assert res.indemnite_maintien == detail.total
