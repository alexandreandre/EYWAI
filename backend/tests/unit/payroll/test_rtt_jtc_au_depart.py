"""RTT et JTC non pris au départ : « néant », avec une alerte « à vérifier selon l'accord ».

Décision du 12/10/2026 : Martine ne paie pas les RTT ni les JTC restants au
départ (le reçu dit « Néant ») ; selon l'accord de la société, ils se paient ou
se perdent. Le bulletin de sortie et le reçu le disent à la gestionnaire.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.modules.employee_exits.application.commands import generate_exit_document
from app.modules.payroll.engine import bulletin as module_bulletin
from app.modules.payroll.engine.bulletin import (
    alertes_des_compteurs_de_conges,
    creer_bulletin_final,
    creer_bulletin_sortie,
)
from app.modules.payroll.engine.calcul_cotisations import calculer_cotisations
from app.modules.payroll.engine.calcul_net import calculer_net_et_impot
from app.modules.payroll.solde_de_tout_compte.common.bulletin_de_sortie import (
    alertes_du_recu,
)
from tests.unit.payroll.helpers import build_test_contexte

pytestmark = pytest.mark.unit

SOLDES = {
    "conges_payes": {"acquis": 10, "pris": 2, "solde": 8},
    "rtt": {"acquis": 10, "pris": 7, "solde": 3},
    "jtc": {"acquis": 2, "pris": 0, "solde": 2},
}


def test_au_depart_les_rtt_et_jtc_restants_appellent_une_alerte():
    alertes = alertes_des_compteurs_de_conges(SOLDES, bulletin_de_sortie=True)
    (alerte,) = [a for a in alertes if a["code"] == "rtt_jtc_non_payes_au_depart"]
    message = alerte["message"]
    assert "3 j de RTT" in message
    assert "2 j de JTC" in message
    assert "« Néant »" in message
    assert "à vérifier selon l'accord" in message
    assert alerte["critique"] is False


def test_hors_depart_aucune_alerte():
    assert not [
        a for a in alertes_des_compteurs_de_conges(SOLDES) if a["code"] == "rtt_jtc_non_payes_au_depart"
    ]


def test_au_depart_sans_reste_aucune_alerte():
    soldes = {"rtt": {"acquis": 10, "pris": 10, "solde": 0}, "jtc": {"acquis": 0, "pris": 0, "solde": 0}}
    assert alertes_des_compteurs_de_conges(soldes, bulletin_de_sortie=True) == []


def test_le_bulletin_de_sortie_porte_l_alerte(monkeypatch):
    monkeypatch.setattr(module_bulletin, "build_solde_conges_pied_de_page", lambda *a, **k: dict(SOLDES))
    ctx = build_test_contexte(salaire_base=2000.0)
    ctx.year = 2026
    ctx.depart_du_mois = True
    lignes, total_sal = calculer_cotisations(ctx, 2000.0)
    nets = calculer_net_et_impot(ctx, 2000.0, lignes, total_sal, [], 0.0)
    final = creer_bulletin_final(ctx, 2000.0, [], lignes, nets, [], 2026, 7)
    assert "rtt_jtc_non_payes_au_depart" in [a.get("code") for a in final["alertes_baremes"]]


@pytest.mark.parametrize("depart", [True, False])
def test_le_bulletin_dit_s_il_est_celui_de_la_sortie(monkeypatch, depart):
    """La remise au salarié en dépend : le bulletin de sortie est remis dès sa validation."""
    monkeypatch.setattr(module_bulletin, "build_solde_conges_pied_de_page", lambda *a, **k: None)
    ctx = build_test_contexte(salaire_base=2000.0)
    ctx.year = 2026
    ctx.depart_du_mois = depart
    lignes, total_sal = calculer_cotisations(ctx, 2000.0)
    nets = calculer_net_et_impot(ctx, 2000.0, lignes, total_sal, [], 0.0)
    final = creer_bulletin_final(ctx, 2000.0, [], lignes, nets, [], 2026, 7)
    assert final["bulletin_de_sortie"] is depart


def test_le_bulletin_aux_indemnites_de_sortie_est_celui_de_la_sortie(monkeypatch):
    monkeypatch.setattr(module_bulletin, "build_solde_conges_pied_de_page", lambda *a, **k: None)
    ctx = build_test_contexte(salaire_base=2000.0)
    ctx.year = 2026
    lignes, total_sal = calculer_cotisations(ctx, 2000.0)
    nets = calculer_net_et_impot(ctx, 2000.0, lignes, total_sal, [], 0.0)
    final = creer_bulletin_sortie(ctx, 2000.0, [], lignes, nets, [], {}, 2026, 7)
    assert final["bulletin_de_sortie"] is True


def test_le_recu_reprend_l_alerte_du_bulletin_de_sortie():
    bulletin = {
        "alertes_baremes": [
            {"code": "rtt_jtc_non_payes_au_depart", "message": "3 j de RTT : à vérifier selon l'accord."},
            {"code": "autre", "message": "sans rapport"},
        ]
    }
    assert alertes_du_recu(bulletin) == ["3 j de RTT : à vérifier selon l'accord."]
    assert alertes_du_recu(None) == []


@patch("app.modules.employee_exits.application.commands.get_exit_document_generator")
@patch("app.modules.employee_exits.application.commands.get_exit_storage_provider")
@patch("app.modules.employee_exits.application.commands.get_company_by_id")
@patch("app.modules.employee_exits.application.commands.ExitDocumentRepository")
@patch("app.modules.employee_exits.application.commands.EmployeeExitRepository")
def test_la_generation_du_recu_rend_l_alerte(
    mock_exit_repo_class, mock_doc_repo_class, mock_company, mock_storage, mock_generator
):
    mock_exit_repo_class.return_value.get_with_employee.return_value = {
        "id": "exit-1",
        "exit_type": "demission",
        "last_working_day": "2026-07-31",
        "calculated_indemnities": None,
        "employees": {"id": "emp-1", "first_name": "Jean", "last_name": "Dupont"},
    }
    mock_company.return_value = {"name": "Test Co"}
    mock_generator.return_value.generate_solde_tout_compte.return_value = b"pdf"
    mock_doc_repo_class.return_value.create.return_value = {"id": "doc-stc"}
    bulletin = {
        "salaire_brut": 2000.0,
        "alertes_baremes": [{"code": "rtt_jtc_non_payes_au_depart", "message": "À vérifier selon l'accord."}],
    }
    with patch(
        "app.modules.payroll.solde_de_tout_compte.common.bulletin_de_sortie.bulletin_du_mois_de_sortie",
        return_value=bulletin,
    ):
        resultat = generate_exit_document("exit-1", "co-1", "solde_tout_compte", "user-1", supabase_client=MagicMock())
    assert resultat["alertes"] == ["À vérifier selon l'accord."]
