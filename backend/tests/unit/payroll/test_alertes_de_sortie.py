"""R-303, R-316, R-317 : ce que le bulletin de sortie rappelle à la gestionnaire.

Alertes en avertissement : aucun montant ne bouge.
- R-303 : solde de congés positif et aucune indemnité compensatrice (C. trav. L3141-28).
- R-317 : solde au CET non transféré : indemnité due (C. trav. L3153-2, 1°).
- R-316 : société sans compteur tenu : solde de modulation suivi hors Martine à vérifier.
"""

from __future__ import annotations

import pytest

from app.modules.payroll.engine import alertes_de_sortie as module
from app.modules.payroll.engine import bulletin as module_bulletin
from app.modules.payroll.engine.bulletin import creer_bulletin_final, creer_bulletin_sortie
from tests.unit.payroll.helpers import build_test_contexte

pytestmark = pytest.mark.unit

NETS = {"net_imposable": 1500.0, "net_a_payer": 1200.0, "montant_impot_pas": 0.0}
ICCP = {"libelle": "Indemnité compensatrice de congés payés", "gain": 500.0}
SOLDES = {
    "conges_payes": {"acquis": 10, "pris": 2, "solde": 6},
    "conges_payes_periode_precedente": {"acquis": 25, "pris": 23, "solde": 2},
}


def _codes(alertes):
    return [a["code"] for a in alertes]


# --- R-303 ---


def test_solde_positif_sans_indemnite_alerte():
    (alerte,) = module.alerte_sortie_sans_iccp(SOLDES, [], iccp_du_dossier=False)
    assert alerte["code"] == "sortie_sans_indemnite_conges"
    assert alerte["critique"] is False
    assert "8 j" in alerte["message"]
    assert "L3141-28" in alerte["message"]


@pytest.mark.parametrize(
    "soldes,lignes,dossier",
    [
        (SOLDES, [ICCP], False),
        (SOLDES, [{"libelle": "CP des CDD", "gain": 80.0}], False),
        (SOLDES, [], True),
        ({"conges_payes": {"solde": 0}}, [], False),
        ({"conges_payes": {"solde": -3}}, [], False),
        (None, [], False),
    ],
)
def test_pas_d_alerte_d_indemnite(soldes, lignes, dossier):
    assert module.alerte_sortie_sans_iccp(soldes, lignes, iccp_du_dossier=dossier) == []


def test_le_bulletin_de_sortie_porte_l_alerte(monkeypatch):
    monkeypatch.setattr(module_bulletin, "build_solde_conges_pied_de_page", lambda *a, **k: dict(SOLDES))
    ctx = build_test_contexte(salaire_base=2000.0)
    ctx.year = 2026
    ctx.depart_du_mois = True
    final = creer_bulletin_final(ctx, 2000.0, [], [], NETS, [], 2026, 7)
    assert "sortie_sans_indemnite_conges" in _codes(final["alertes_baremes"])


def test_le_bulletin_hors_depart_ne_dit_rien(monkeypatch):
    monkeypatch.setattr(module_bulletin, "build_solde_conges_pied_de_page", lambda *a, **k: dict(SOLDES))
    ctx = build_test_contexte(salaire_base=2000.0)
    ctx.year = 2026
    final = creer_bulletin_final(ctx, 2000.0, [], [], NETS, [], 2026, 7)
    assert "sortie_sans_indemnite_conges" not in _codes(final["alertes_baremes"])


def test_l_indemnite_versee_par_le_dossier_ne_declenche_pas_l_alerte(monkeypatch):
    monkeypatch.setattr(module_bulletin, "build_solde_conges_pied_de_page", lambda *a, **k: dict(SOLDES))
    ctx = build_test_contexte(salaire_base=2000.0)
    ctx.year = 2026
    ctx.depart_du_mois = True
    indemnites = {"indemnite_conges": {"montant": 500.0, "description": "ICCP", "details": {}}}
    final = creer_bulletin_sortie(ctx, 2000.0, [], [], NETS, [], indemnites, 2026, 7)
    assert "sortie_sans_indemnite_conges" not in _codes(final["alertes_baremes"])


# --- R-317 ---


def test_solde_cet_appelle_une_alerte(monkeypatch):
    monkeypatch.setattr(module, "_solde_cet_en_heures", lambda *a: 14.0)
    (alerte,) = module.alerte_cet_au_depart("e1", "c1")
    assert alerte["code"] == "cet_a_payer_au_depart"
    assert alerte["critique"] is False
    assert "14 h" in alerte["message"]
    assert "L3153-2" in alerte["message"]


@pytest.mark.parametrize("solde", [0.0, -2.0])
def test_cet_vide_pas_d_alerte(monkeypatch, solde):
    monkeypatch.setattr(module, "_solde_cet_en_heures", lambda *a: solde)
    assert module.alerte_cet_au_depart("e1", "c1") == []


# --- R-316 ---


@pytest.mark.parametrize(
    "reglages,mouvements,attendu",
    [
        ({"hour_account_enabled": True, "hs_routing_policy": "pay_all"}, [], True),
        ({"hour_account_enabled": True, "hs_routing_policy": "pay_all"}, [{"id": "m1"}], False),
        ({"hour_account_enabled": True, "hs_routing_policy": "account_all"}, [], False),
        ({"hour_account_enabled": False, "hs_routing_policy": "pay_all"}, [], False),
        (None, [], False),
    ],
)
def test_modulation_hors_martine(monkeypatch, reglages, mouvements, attendu):
    monkeypatch.setattr(module, "_reglages_modulation", lambda *a: reglages)
    monkeypatch.setattr(module, "_mouvements_du_compteur", lambda *a: mouvements)
    alertes = module.alerte_modulation_au_depart("e1", "c1")
    assert _codes(alertes) == (["solde_modulation_a_verifier_au_depart"] if attendu else [])
    if attendu:
        assert alertes[0]["critique"] is False


# --- Lecture ratée : on le dit ---


def test_une_lecture_ratee_se_dit(monkeypatch):
    def rate(*a):
        raise RuntimeError("coupure")

    monkeypatch.setattr(module, "_solde_cet_en_heures", rate)
    monkeypatch.setattr(module, "_reglages_modulation", lambda *a: None)
    alertes = module.alertes_de_sortie("e1", "c1", None, [], iccp_du_dossier=False)
    assert _codes(alertes) == ["compteurs_de_depart_illisibles"]
    assert alertes[0]["critique"] is False
