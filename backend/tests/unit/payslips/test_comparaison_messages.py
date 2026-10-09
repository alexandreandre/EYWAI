"""Messages de la comparaison : pourcentages à la française, une seule phrase pour « pas de N-1 ».

Les messages R01 à R05 écrivaient « 14.0% » (point, sans espace) à côté de
« (seuil critique > 10 %) » : un seul format, « 14,0 % ».
"""

from __future__ import annotations

from app.modules.payslips.domain.comparison_engine import compute_comparison


def _ctx(avec_n1: bool = True) -> dict:
    return {
        "bulletin_n_id": "n",
        "month_n": 10,
        "year_n": 2026,
        "bulletin_n1_id": "n1" if avec_n1 else None,
        "month_n1": 9 if avec_n1 else None,
        "year_n1": 2026 if avec_n1 else None,
        "is_forfait_jour": False,
        "has_contract_change": False,
        "has_declared_advance": None,
        "recent_nets_asc": [],
    }


def _bulletin(brut: float, net: float, cotisations: float) -> dict:
    return {
        "salaire_brut": brut,
        "net_a_payer": net,
        "structure_cotisations": {"total_salarial": cotisations},
        "synthese_net": {},
        "calcul_du_brut": [
            {"libelle": "Salaire de base", "quantite": 151.67, "taux": 13.0, "gain": brut, "perte": None}
        ],
        "total_heures_supp": 0.0,
    }


def _messages(n: dict, n1: dict | None) -> dict[str, str]:
    resultat = compute_comparison(n, n1, _ctx(avec_n1=n1 is not None))
    return {a.rule_id: a.message for a in resultat.alerts}


def test_r01_r03_r05_ecrivent_les_pourcentages_a_la_francaise():
    messages = _messages(_bulletin(2200.0, 1710.0, 540.0), _bulletin(2000.0, 1500.0, 480.0))
    assert messages["R01"] == "Le salaire brut a varié de 10,0 % par rapport au dernier bulletin validé."
    assert messages["R03"] == "Le net à payer a varié de 14,0 % (seuil critique > 10 %)."
    assert messages["R05"] == "Variation des cotisations salariales de 12,5 % (seuil > 8 %)."


def test_r02_r04_ecrivent_les_pourcentages_a_la_francaise():
    messages = _messages(_bulletin(2060.0, 1620.0, 480.0), _bulletin(2000.0, 1500.0, 480.0))
    assert messages["R02"] == "Variation du salaire brut de 3,0 % (seuil d'avertissement 1–5 %)."
    assert messages["R04"] == "Le net à payer a varié de 8,0 % (seuil d'avertissement 5–10 %)."

