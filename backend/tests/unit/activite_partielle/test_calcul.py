"""Activité partielle : indemnité horaire et lignes du mois (retour d'Elsa du 16/11)."""

from __future__ import annotations

import pytest

from app.modules.activite_partielle.domain.calcul import (
    calculer,
    refus_periode,
    taux_horaire_du_contrat,
)


def test_taux_horaire_du_contrat():
    assert taux_horaire_du_contrat(
        {"type": "mensuel", "valeur": 2166.67}, "35.00"
    ) == pytest.approx(14.2857, abs=1e-3)
    assert taux_horaire_du_contrat({"valeur": None}, 35) is None
    assert taux_horaire_du_contrat(0, 35) is None


def test_soixante_pour_cent_du_salaire_horaire():
    c = calculer(14, 20.0)
    assert c.indemnite_horaire == 12.0
    assert c.retenue == 280.0
    assert c.indemnite == 168.0
    assert "60 %" in c.regle


def test_plancher_pour_un_petit_salaire():
    # 14,29 € de l'heure : 60 % = 8,57 € < 9,74 € → le plancher.
    c = calculer(56, 14.2857)
    assert c.indemnite_horaire == 9.74
    assert c.indemnite == 545.44
    assert "plancher" in c.regle


def test_plafond_pour_un_gros_salaire():
    c = calculer(7, 80.0)
    assert c.indemnite_horaire == 33.24
    assert "plafond" in c.regle


def test_jamais_plus_que_le_salaire_horaire():
    # Temps partiel ou apprenti sous le plancher : l'indemnité s'arrête au salaire horaire.
    c = calculer(10, 9.0)
    assert c.indemnite_horaire == 9.0
    assert c.indemnite == 90.0


def test_taux_d_accord():
    assert calculer(10, 30.0, taux_indemnite=70).indemnite_horaire == 21.0


def test_periode():
    reglage = {"active": True, "date_debut": "2026-06-01", "date_fin": "2026-11-30"}
    assert refus_periode(reglage, 2026, 6) is None
    assert refus_periode(reglage, 2026, 11) is None
    assert "avant" in refus_periode(reglage, 2026, 5)
    assert "après" in refus_periode(reglage, 2026, 12)
    assert "pas activée" in refus_periode({"active": False}, 2026, 6)
