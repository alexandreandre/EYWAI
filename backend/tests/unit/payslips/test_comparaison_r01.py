"""R01 ne bloque plus la validation.

R01 compare le brut TOTAL au dernier bulletin validé, heures sup, primes et
absences comprises, et le contexte dit toujours « pas de changement de
contrat » (`has_contract_change: False`, comparison_service). Un mois avec
quelques heures sup dépasse 5 % de brut : la règle demandait un acquittement
pour presque chaque bulletin variable, dès qu'un mois précédent est validé.
Calculer un changement de contrat n'y changerait rien : ce sont les variables
du mois qui font bouger le brut. R01 devient un avertissement ; R03 (net à plus
de 10 %) reste critique et garde le filet.
"""

from __future__ import annotations

from app.modules.payslips.domain.comparison_engine import compute_comparison


def _ctx() -> dict:
    return {
        "bulletin_n_id": "n",
        "month_n": 10,
        "year_n": 2026,
        "bulletin_n1_id": "n1",
        "month_n1": 9,
        "year_n1": 2026,
        "is_forfait_jour": False,
        "has_contract_change": False,
        "has_declared_advance": None,
        "recent_nets_asc": [],
    }


def _bulletin(brut: float, net: float) -> dict:
    return {
        "salaire_brut": brut,
        "net_a_payer": net,
        "structure_cotisations": {"total_salarial": 400.0},
        "synthese_net": {},
        "calcul_du_brut": [{"type": "travail_base", "libelle": "Salaire de base", "quantite": 151.67}],
        "total_heures_supp": 0.0,
    }


def test_un_mois_d_heures_sup_ne_bloque_pas_la_validation():
    # Brut +8 % (heures sup), net +8 % : sous le seuil critique du net.
    resultat = compute_comparison(_bulletin(1944.0, 1512.0), _bulletin(1800.0, 1400.0), _ctx())
    r01 = [a for a in resultat.alerts if a.rule_id == "R01"]
    assert len(r01) == 1
    assert r01[0].level == "AVERTISSEMENT"
    assert resultat.has_critical is False


def test_r01_ne_pretend_plus_avoir_cherche_un_changement_de_contrat():
    resultat = compute_comparison(_bulletin(1944.0, 1512.0), _bulletin(1800.0, 1400.0), _ctx())
    r01 = next(a for a in resultat.alerts if a.rule_id == "R01")
    assert "contrat" not in r01.message


def test_le_net_a_plus_de_10_pourcent_reste_critique():
    resultat = compute_comparison(_bulletin(2100.0, 1600.0), _bulletin(1800.0, 1400.0), _ctx())
    r03 = [a for a in resultat.alerts if a.rule_id == "R03"]
    assert len(r03) == 1
    assert r03[0].level == "CRITIQUE"
    assert resultat.has_critical is True
