"""Messages d'alerte R01 à R12 : nombres à la française, et R06/R07 disent la différence en lignes.

Constat du 09/10/2026 : R09 « 21.33 h » (point) ; R07 « Variation 1,0 % » à
propos de deux nombres de lignes, ce qui ne veut rien dire pour une gestionnaire.
"""

from __future__ import annotations

from app.modules.payslips.domain.comparison_engine import (
    compute_comparison,
    comparison_result_to_dict,
)


def _ctx(**extra) -> dict:
    return {
        "bulletin_n_id": "n", "month_n": 10, "year_n": 2026,
        "bulletin_n1_id": "n1", "month_n1": 9, "year_n1": 2026,
        "is_forfait_jour": False, "has_contract_change": False,
        "has_declared_advance": None, "recent_nets_asc": [], **extra,
    }


def _bulletin(lignes: list[dict], **champs) -> dict:
    return {
        "salaire_brut": 2000.0,
        "net_a_payer": 1500.0,
        "structure_cotisations": {"total_salarial": 480.0},
        "synthese_net": {},
        "calcul_du_brut": lignes,
        "total_heures_supp": 0.0,
        **champs,
    }


_BASE = {"libelle": "Salaire de base", "quantite": 151.67, "taux": 13.0, "gain": 2000.0, "perte": None}
_PRIME = {"libelle": "Prime exceptionnelle", "quantite": 1.0, "taux": None, "gain": 100.0, "perte": None}


def _alertes(n: dict, n1: dict | None, **ctx) -> dict[str, dict]:
    res = comparison_result_to_dict(compute_comparison(n, n1, _ctx(**ctx)))
    return {a["rule_id"]: a for a in res["alerts"]}


def test_r09_ecrit_les_heures_avec_une_virgule():
    sup = {"libelle": "Heures suppl. majorées à 25%", "quantite": 21.33, "taux": 16.0, "gain": 341.0, "perte": None}
    alertes = _alertes(_bulletin([_BASE, sup]), _bulletin([_BASE]))
    assert alertes["R09"]["message"] == "Heures supplémentaires élevées : 21,33 h (> 20 h)."


def test_r08_ecrit_les_heures_avec_une_virgule():
    absence = {"libelle": "Absence maladie du 01/10 au 31/10", "quantite": 100.0, "taux": 13.0, "gain": None, "perte": 1300.0, "is_arret_maladie": True}
    alertes = _alertes(_bulletin([_BASE, absence]), None, bulletin_n1_id=None)
    message = alertes["R08"]["message"]
    assert "(51,67 h)" in message
    assert "(151,67 h)" in message


def test_r10_et_r11_ecrivent_les_euros_avec_une_virgule():
    n = _bulletin([_BASE], synthese_net={"acompte_verse": 150.5})
    alertes = _alertes(n, _bulletin([_BASE]), recent_nets_asc=[1900.0, 1800.0, 1700.5, 1600.25], has_declared_advance=False)
    assert "1 900,00 → 1 800,00 → 1 700,50 → 1 600,25 €" in alertes["R10"]["message"]
    assert "(150,50 €)" in alertes["R11"]["message"]


def test_r07_dit_la_difference_en_lignes_pas_en_pourcentage():
    alertes = _alertes(_bulletin([_BASE, _PRIME]), _bulletin([_BASE]))
    r07 = alertes["R07"]
    assert "1 ligne de plus que le mois de référence" in r07["message"]
    assert "Prime exceptionnelle" in r07["message"]
    assert r07["unite"] == "nombre"


def test_r07_accorde_le_pluriel():
    deux = {"libelle": "Prime de caisse", "quantite": 1.0, "taux": None, "gain": 50.0, "perte": None}
    alertes = _alertes(_bulletin([_BASE, _PRIME, deux]), _bulletin([_BASE]))
    assert "2 lignes de plus que le mois de référence" in alertes["R07"]["message"]


def test_r06_dit_la_difference_en_lignes():
    alertes = _alertes(_bulletin([_BASE]), _bulletin([_BASE, _PRIME]))
    assert "1 ligne de moins que le mois de référence" in alertes["R06"]["message"]
