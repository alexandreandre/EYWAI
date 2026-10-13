"""Congé ou RTT posé au-delà du solde : payé en entier, et le bulletin le dit.

Décision du 12/10/2026 : le bulletin paie déjà chaque jour de congé posé, même
au-delà du solde. On ne le retire pas : une alerte le dit à la gestionnaire,
qui pose elle-même un congé sans solde si l'excédent ne doit pas être payé.
Le compteur décompte l'excédent : le solde passe en négatif, et le bulletin
garde de combien.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.modules.absences.domain.rules import compute_cp_balances_for_bulletin
from app.modules.payroll.engine import bulletin as module_bulletin
from app.modules.payroll.engine.bulletin import (
    alertes_des_compteurs_de_conges,
    creer_bulletin_final,
)
from app.modules.payroll.engine.calcul_cotisations import calculer_cotisations
from app.modules.payroll.engine.calcul_net import calculer_net_et_impot
from tests.unit.payroll.helpers import build_test_contexte

pytestmark = pytest.mark.unit


def _conges(jours: list[str]) -> list[dict]:
    return [
        {
            "type": "conge_paye",
            "status": "validated",
            "selected_days": jours,
            "jours_payes": float(len(jours)),
        }
    ]


def test_le_compteur_du_bulletin_garde_le_depassement():
    # Entré le 01/06 : juin et juillet acquis (5 j ouvrables), 7 j posés en juillet.
    jours = [f"2026-07-{j:02d}" for j in (6, 7, 8, 9, 10, 13, 15)]
    soldes = compute_cp_balances_for_bulletin(
        date(2026, 6, 1), _conges(jours), date(2026, 7, 31)
    )
    courante = soldes["periode_courante"]
    assert courante["solde"] == 0.0
    assert courante["depassement"] == 2.0


def test_sans_depassement_le_compteur_ne_change_pas():
    soldes = compute_cp_balances_for_bulletin(
        date(2026, 6, 1), _conges(["2026-07-06"]), date(2026, 7, 31)
    )
    assert "depassement" not in soldes["periode_courante"]


def test_l_alerte_dit_que_l_excedent_est_paye():
    alertes = alertes_des_compteurs_de_conges(
        {"conges_payes": {"acquis": 5, "pris": 7, "solde": 0, "depassement": 2.0}}
    )
    assert [a["code"] for a in alertes] == ["conge_au_dela_du_solde"]
    message = alertes[0]["message"]
    assert "2 j" in message
    assert "payés en entier" in message
    assert "congé sans solde" in message
    assert alertes[0]["critique"] is False


def test_l_alerte_vaut_aussi_pour_les_rtt():
    alertes = alertes_des_compteurs_de_conges(
        {"rtt": {"acquis": 10, "pris": 10.5, "solde": 0, "depassement": 0.5}}
    )
    assert [a["code"] for a in alertes] == ["rtt_au_dela_du_solde"]
    assert "0,5 j" in alertes[0]["message"]
    assert "RTT" in alertes[0]["message"]


def test_aucune_alerte_quand_les_soldes_suffisent():
    assert alertes_des_compteurs_de_conges(
        {"conges_payes": {"acquis": 5, "pris": 1, "solde": 4}, "rtt": {"acquis": 0, "pris": 0, "solde": 0}}
    ) == []
    assert alertes_des_compteurs_de_conges(None) == []


def test_le_bulletin_porte_l_alerte(monkeypatch):
    monkeypatch.setattr(
        module_bulletin,
        "build_solde_conges_pied_de_page",
        lambda *a, **k: {"conges_payes": {"acquis": 5, "pris": 7, "solde": 0, "depassement": 2.0}},
    )
    ctx = build_test_contexte(salaire_base=2000.0)
    ctx.year = 2026
    lignes, total_sal = calculer_cotisations(ctx, 2000.0)
    nets = calculer_net_et_impot(ctx, 2000.0, lignes, total_sal, [], 0.0)
    final = creer_bulletin_final(ctx, 2000.0, [], lignes, nets, [], 2026, 7)
    codes = [a.get("code") for a in final["alertes_baremes"]]
    assert "conge_au_dela_du_solde" in codes
