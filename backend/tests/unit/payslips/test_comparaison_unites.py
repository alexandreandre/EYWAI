"""L'onglet « Comparaison N-1 » affiche des heures en heures, pas en euros.

Constat du 09/10/2026 (bulletin d'un salarié à 39 h) : « Heures travaillées
(travail_base) 151,67 € », et « Heures supplémentaires 0,00 € » alors que le
bulletin porte 17,33 h d'heures sup structurelles, comptées partout ailleurs
(liste du mois, « Ce qui a changé par rapport au mois dernier »).
"""

from __future__ import annotations

from app.modules.payslips.domain.comparison_engine import (
    comparison_result_to_dict,
    compute_comparison,
)


def _ctx() -> dict:
    return {
        "bulletin_n_id": "n", "month_n": 10, "year_n": 2026,
        "bulletin_n1_id": "n1", "month_n1": 9, "year_n1": 2026,
        "is_forfait_jour": False, "has_contract_change": False,
        "has_declared_advance": None, "recent_nets_asc": [],
    }


def _bulletin_39h(net: float = 1951.19) -> dict:
    return {
        "salaire_brut": 2450.0,
        "net_a_payer": net,
        "structure_cotisations": {"total_salarial": 475.95},
        "synthese_net": {},
        "calcul_du_brut": [
            {"libelle": "Salaire de base", "quantite": 151.67, "taux": 14.1347, "gain": 2143.81, "perte": None},
            {"libelle": "Heures suppl. structurelles majorées à 25%", "quantite": 17.33, "taux": 17.6684, "gain": 306.19, "perte": None},
            {"libelle": "SOUS-TOTAL SALAIRE CONTRACTUEL", "quantite": 169.0, "taux": None, "gain": 2450.0, "perte": None},
        ],
        "total_heures_supp": 0.0,
    }


def _lignes() -> dict:
    res = comparison_result_to_dict(compute_comparison(_bulletin_39h(), _bulletin_39h(), _ctx()))
    return {ligne["libelle"]: ligne for ligne in res["lines"]}


def test_les_heures_ont_l_unite_heure():
    lignes = _lignes()
    assert lignes["Heures travaillées"]["unite"] == "h"
    assert lignes["Heures supplémentaires"]["unite"] == "h"


def test_les_montants_ont_l_unite_euro():
    lignes = _lignes()
    assert lignes["Salaire brut"]["unite"] == "eur"
    assert lignes["Net à payer"]["unite"] == "eur"


def test_l_intitule_ne_montre_plus_le_nom_technique():
    assert not any("travail_base" in libelle for libelle in _lignes())


def test_les_heures_sup_structurelles_sont_comptees():
    assert _lignes()["Heures supplémentaires"]["value_n"] == 17.33


def test_une_alerte_sur_des_heures_porte_l_unite_heure():
    bulletin = _bulletin_39h()
    bulletin["calcul_du_brut"].append(
        {"libelle": "Absence maladie du 01/10 au 31/10", "quantite": 151.67, "taux": 14.1347, "gain": None, "perte": 2143.81, "is_arret_maladie": True}
    )
    res = comparison_result_to_dict(compute_comparison(bulletin, None, {**_ctx(), "bulletin_n1_id": None}))
    r08 = next(a for a in res["alerts"] if a["rule_id"] == "R08")
    assert r08["unite"] == "h"


def test_une_alerte_sur_le_net_porte_l_unite_euro():
    res = comparison_result_to_dict(compute_comparison(_bulletin_39h(net=2300.0), _bulletin_39h(), _ctx()))
    r03 = next(a for a in res["alerts"] if a["rule_id"] == "R03")
    assert r03["unite"] == "eur"
