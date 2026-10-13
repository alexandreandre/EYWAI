"""Saisie sur salaire entrée en variable « sur le net » : une alerte au-delà de la
quotité saisissable, sans plafond.

Les saisies réelles (Colorplast, Comitech, LEWIS, Mont-Blanc) sont presque toutes
saisies en variables « Retenue sur le net », que rien ne compare à la quotité
saisissable. Décision du 12/10/2026 : le bulletin alerte quand elles la
dépassent, et retient le montant tel quel.
"""

from __future__ import annotations

import copy

import pytest

from app.modules.saisies_avances.application import service

pytestmark = pytest.mark.unit

BAREME = {
    "par_annee": {
        "2026": {
            "tranches": [
                {"jusqu_a_annuel": 4480, "fraction": "1/20"},
                {"jusqu_a_annuel": 8730, "fraction": "1/10"},
                {"jusqu_a_annuel": 13000, "fraction": "1/5"},
                {"jusqu_a_annuel": 17230, "fraction": "1/4"},
                {"jusqu_a_annuel": 21470, "fraction": "1/3"},
                {"jusqu_a_annuel": 25810, "fraction": "2/3"},
                {"jusqu_a_annuel": None, "fraction": "1"},
            ],
            "majoration_annuelle_par_personne_a_charge": 1740,
        }
    },
    "solde_insaisissable": [{"date_debut": "2026-04-01", "montant_mensuel": 651.69}],
}


@pytest.fixture()
def enrichir(monkeypatch):
    monkeypatch.setattr(service, "get_seizures_for_period", lambda *a, **k: [])
    monkeypatch.setattr(service, "get_advances_to_repay", lambda *a, **k: [])
    monkeypatch.setattr(service, "get_bareme_quotite_saisissable", lambda: copy.deepcopy(BAREME))

    def _enrichir(retenues):
        monkeypatch.setattr(service, "get_retenues_sur_le_net_du_mois", lambda *a, **k: retenues)
        # Le moteur a déjà retiré la retenue du net : 1 500 € de base saisissable.
        total = sum(-float(r["amount"]) for r in retenues if float(r["amount"]) < 0)
        bulletin = {"net_a_payer": 1500.0 - total, "synthese_net": {"acompte_verse": total}}
        return service.enrich_payslip(bulletin, "emp-1", 2026, 10, payslip_id=None)

    return _enrichir


def _alertes(bulletin):
    return [a for a in bulletin.get("alertes_baremes") or [] if a.get("code") == "saisie_en_variable_au_dela_de_la_quotite"]


def test_au_dela_de_la_quotite_le_bulletin_alerte_sans_plafonner(enrichir):
    bulletin = enrichir([{"name": "SAISIE SGC", "amount": -300.0, "sur_le_net": True}])
    (alerte,) = _alertes(bulletin)
    assert "« SAISIE SGC »" in alerte["message"]
    assert "300,00 €" in alerte["message"]
    assert "quotité saisissable" in alerte["message"]
    assert "retenu tel quel" in alerte["message"]
    assert alerte["critique"] is False
    # Rien n'est plafonné : le net ne bouge pas.
    assert bulletin["net_a_payer"] == 1200.0


def test_sous_la_quotite_aucune_alerte(enrichir):
    assert _alertes(enrichir([{"name": "Saisie sur salaire", "amount": -100.0, "sur_le_net": True}])) == []


def test_une_retenue_qui_n_est_pas_une_saisie_ne_compte_pas(enrichir):
    assert _alertes(enrichir([{"name": "Acompte d'octobre", "amount": -800.0, "sur_le_net": True}])) == []
