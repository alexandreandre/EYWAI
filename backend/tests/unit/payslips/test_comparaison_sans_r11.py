"""La règle R11 (acompte sans avance déclarée) est retirée : elle ne se déclenchait jamais."""

from __future__ import annotations

from app.modules.payslips.domain.comparison_engine import (
    compute_comparison,
    comparison_result_to_dict,
)


def test_aucune_alerte_r11_meme_avec_un_acompte_sans_avance():
    base = {"libelle": "Salaire de base", "quantite": 151.67, "taux": 13.0, "gain": 2000.0, "perte": None}
    bulletin = {
        "salaire_brut": 2000.0,
        "net_a_payer": 1500.0,
        "structure_cotisations": {"total_salarial": 480.0},
        "synthese_net": {"acompte_verse": 150.5},
        "calcul_du_brut": [base],
        "total_heures_supp": 0.0,
    }
    ctx = {
        "bulletin_n_id": "n", "month_n": 10, "year_n": 2026,
        "is_forfait_jour": False, "has_contract_change": False,
        "has_declared_advance": False, "recent_nets_asc": [],
    }
    res = comparison_result_to_dict(compute_comparison(bulletin, None, ctx))
    assert "R11" not in {a["rule_id"] for a in res["alerts"]}
