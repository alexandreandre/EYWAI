"""Tests unitaires du moteur de comparaison payslips (domaine pur)."""

from __future__ import annotations

import copy


from app.modules.payslips.domain.comparison_engine import compute_comparison


def _ctx(**overrides):
    base = {
        "bulletin_n_id": "pid-n",
        "month_n": 6,
        "year_n": 2025,
        "bulletin_n1_id": "pid-n1",
        "month_n1": 5,
        "year_n1": 2025,
        "is_forfait_jour": False,
        "has_contract_change": False,
        "has_declared_advance": None,
        "recent_nets_asc": [],
    }
    base.update(overrides)
    return base


def _bulletin(
    salaire_brut: float = 3000.0,
    net_a_payer: float = 2400.0,
    total_salarial: float = 500.0,
    calcul_du_brut: list | None = None,
    heures_supp: float = 0.0,
    acompte: float = 0.0,
    types_travail: tuple[float, ...] = (151.0,),
) -> dict:
    lines = []
    for h in types_travail:
        lines.append({"type": "travail_base", "libelle": "H. travail", "quantite": h})
    if calcul_du_brut is not None:
        lines = calcul_du_brut
    sn = {"acompte_verse": acompte}
    sc = {"total_salarial": total_salarial}
    return {
        "salaire_brut": salaire_brut,
        "net_a_payer": net_a_payer,
        "structure_cotisations": sc,
        "synthese_net": sn,
        "calcul_du_brut": lines,
        "total_heures_supp": heures_supp,
    }


def test_t1_r01_brut_variation_over_5_percent_critical():
    n = _bulletin(salaire_brut=2000.0)
    n1 = _bulletin(salaire_brut=1800.0)
    res = compute_comparison(n, n1, _ctx())
    r01 = [a for a in res.alerts if a.rule_id == "R01"]
    assert len(r01) == 1
    assert r01[0].level == "CRITIQUE"


def test_t2_r01_not_triggered_when_variation_at_most_5_percent():
    n = _bulletin(salaire_brut=1020.0)
    n1 = _bulletin(salaire_brut=1000.0)
    res = compute_comparison(n, n1, _ctx())
    assert not any(a.rule_id == "R01" for a in res.alerts)


def test_t3_r03_net_variation_over_10_percent_critical():
    n = _bulletin(net_a_payer=1200.0)
    n1 = _bulletin(net_a_payer=1000.0)
    res = compute_comparison(n, n1, _ctx())
    r03 = [a for a in res.alerts if a.rule_id == "R03"]
    assert len(r03) == 1
    assert r03[0].level == "CRITIQUE"


def test_t4_r08_not_triggered_when_forfait_jour():
    n = _bulletin(types_travail=(10.0,))
    n1 = _bulletin(types_travail=(151.0,))
    res = compute_comparison(
        n,
        n1,
        _ctx(is_forfait_jour=True),
    )
    assert not any(a.rule_id == "R08" for a in res.alerts)


def test_t5_r12_when_no_bulletin_n1():
    n = _bulletin()
    res = compute_comparison(n, None, _ctx(bulletin_n1_id=None, month_n1=None, year_n1=None))
    r12 = [a for a in res.alerts if a.rule_id == "R12"]
    assert len(r12) == 1
    assert r12[0].level == "INFO"


def test_t6_r06_missing_brut_line_from_n1():
    n = _bulletin(
        calcul_du_brut=[
            {"type": "travail_base", "libelle": "Salaire base", "quantite": 151.0}
        ]
    )
    n1 = _bulletin(
        calcul_du_brut=[
            {"type": "travail_base", "libelle": "Salaire base", "quantite": 151.0},
            {"libelle": "Prime ancienneté", "quantite": 0.0},
        ]
    )
    res = compute_comparison(n, n1, _ctx())
    r06 = [a for a in res.alerts if a.rule_id == "R06"]
    assert len(r06) == 1
    assert "Prime ancienneté" in r06[0].message


def test_t7_has_critical_true_when_critical_alert():
    n = _bulletin(salaire_brut=2000.0)
    n1 = _bulletin(salaire_brut=1800.0)
    res = compute_comparison(n, n1, _ctx())
    assert res.has_critical is True


def test_t8_has_critical_false_when_only_info():
    n = _bulletin()
    res = compute_comparison(n, None, _ctx(bulletin_n1_id=None, month_n1=None, year_n1=None))
    assert res.has_critical is False
    assert any(a.rule_id == "R12" for a in res.alerts)


def test_t9_r02_brut_variation_between_1_and_5_percent_warning():
    n = _bulletin(salaire_brut=1030.0)
    n1 = _bulletin(salaire_brut=1000.0)
    res = compute_comparison(n, n1, _ctx())
    r02 = [a for a in res.alerts if a.rule_id == "R02"]
    assert len(r02) == 1
    assert r02[0].level == "AVERTISSEMENT"
    assert not any(a.rule_id == "R01" for a in res.alerts)


def test_t10_r04_net_variation_between_5_and_10_percent_warning():
    n = _bulletin(salaire_brut=3000.0, net_a_payer=1070.0)
    n1 = _bulletin(salaire_brut=3000.0, net_a_payer=1000.0)
    res = compute_comparison(n, n1, _ctx())
    r04 = [a for a in res.alerts if a.rule_id == "R04"]
    assert len(r04) == 1
    assert r04[0].level == "AVERTISSEMENT"
    assert not any(a.rule_id == "R03" for a in res.alerts)


def test_t11_r05_cotisations_variation_over_8_percent_warning():
    n = _bulletin(salaire_brut=3000.0, net_a_payer=2400.0, total_salarial=600.0)
    n1 = _bulletin(salaire_brut=3000.0, net_a_payer=2400.0, total_salarial=500.0)
    res = compute_comparison(n, n1, _ctx())
    r05 = [a for a in res.alerts if a.rule_id == "R05"]
    assert len(r05) == 1
    assert r05[0].level == "AVERTISSEMENT"


def test_t12_r09_heures_supp_over_20_info():
    n = _bulletin(heures_supp=25.0)
    n1 = _bulletin(heures_supp=0.0)
    res = compute_comparison(n, n1, _ctx())
    r09 = [a for a in res.alerts if a.rule_id == "R09"]
    assert len(r09) == 1
    assert r09[0].level == "INFO"


def test_t13_r07_new_brut_line_in_n_info():
    n = _bulletin(
        calcul_du_brut=[
            {"type": "travail_base", "libelle": "Salaire base", "quantite": 151.0},
            {"libelle": "Prime exceptionnelle", "quantite": 0.0},
        ]
    )
    n1 = _bulletin(
        calcul_du_brut=[
            {"type": "travail_base", "libelle": "Salaire base", "quantite": 151.0},
        ]
    )
    res = compute_comparison(n, n1, _ctx())
    r07 = [a for a in res.alerts if a.rule_id == "R07"]
    assert len(r07) == 1
    assert r07[0].level == "INFO"
    assert "Prime exceptionnelle" in r07[0].message


def test_t14_no_alerts_when_bulletins_identical_with_n1():
    n = _bulletin()
    n1 = copy.deepcopy(n)
    res = compute_comparison(n, n1, _ctx())
    assert res.alerts == []


def test_t15_has_critical_false_when_only_warning_and_info_alerts():
    n = _bulletin(salaire_brut=1030.0, net_a_payer=1070.0)
    n1 = _bulletin(salaire_brut=1000.0, net_a_payer=1000.0)
    res = compute_comparison(n, n1, _ctx())
    assert res.has_critical is False
    assert any(a.rule_id == "R02" for a in res.alerts)
    assert any(a.rule_id == "R04" for a in res.alerts)
    assert not any(a.level == "CRITIQUE" for a in res.alerts)


def test_t16_delta_pct_brut_line_matches_expected():
    n = _bulletin(salaire_brut=2600.0)
    n1 = _bulletin(salaire_brut=2500.0)
    res = compute_comparison(n, n1, _ctx())
    line = next(L for L in res.lines if L.libelle == "Salaire brut")
    assert line.delta_pct is not None
    assert abs(line.delta_pct - 4.0) < 0.1
