"""R08 lit les heures sur les lignes que le moteur écrit vraiment.

R08 (« heures travaillées < 50 % du volume contractuel », critique) additionnait
les lignes de `calcul_du_brut` de type `travail_base`. Le moteur n'écrit aucun
`type` sur ses lignes : « Salaire de base » n'a que libelle, quantite, taux,
gain, perte. Tout bulletin lisait 0,00 h et sa validation était refusée tant
que l'alerte n'était pas acquittée (constaté le 06/10/2026, aucun bulletin
validé depuis le 01/09). La référence était aussi figée à 151,67 h : un temps
partiel était toujours sous 50 %.

Sur ces lignes, la référence est l'horaire du « Salaire de base » moins une
entrée ou une sortie en cours de mois ; les heures non travaillées sont les
absences retenues (arrêt, absence non rémunérée ou injustifiée, férié non
payé). Congés payés et événement familial sont du temps payé : ils ne
déclenchent pas R08.
"""

from __future__ import annotations

from app.modules.payslips.domain.comparison_engine import compute_comparison


def _ctx() -> dict:
    return {
        "bulletin_n_id": "n",
        "month_n": 10,
        "year_n": 2026,
        "bulletin_n1_id": None,
        "month_n1": None,
        "year_n1": None,
        "is_forfait_jour": False,
        "has_contract_change": False,
        "has_declared_advance": None,
        "recent_nets_asc": [],
    }


def _base(heures: float = 151.67) -> dict:
    return {"libelle": "Salaire de base", "quantite": heures, "taux": 13.8458, "gain": 2100.0, "perte": None}


def _retenue(libelle: str, heures: float, **autres) -> dict:
    return {"libelle": libelle, "quantite": heures, "taux": 13.8458, "gain": None, "perte": round(heures * 13.8458, 2), **autres}


def _bulletin(*lignes: dict) -> dict:
    return {
        "salaire_brut": 2100.0,
        "net_a_payer": 1640.0,
        "structure_cotisations": {"total_salarial": 460.0},
        "synthese_net": {},
        "calcul_du_brut": list(lignes),
        "total_heures_supp": 0.0,
    }


def _r08(bulletin: dict):
    return [a for a in compute_comparison(bulletin, None, _ctx()).alerts if a.rule_id == "R08"]


def test_un_mois_complet_ne_declenche_pas_r08():
    assert _r08(_bulletin(_base())) == []


def test_un_temps_partiel_se_compare_a_son_propre_horaire():
    assert _r08(_bulletin(_base(35.0))) == []


def test_une_entree_en_cours_de_mois_ne_declenche_pas_r08():
    bulletin = _bulletin(_base(), _retenue("Absence pour entrée ou sortie", 80.0))
    assert _r08(bulletin) == []


def test_des_conges_payes_ne_declenchent_pas_r08():
    bulletin = _bulletin(_base(), _retenue("Absence congés payés (15 jours : 01/08 au 21/08)", 105.0))
    assert _r08(bulletin) == []


def test_un_arret_de_tout_le_mois_declenche_r08_avec_les_vraies_heures():
    bulletin = _bulletin(_base(), _retenue("Absence maladie du 01/10 au 31/10", 151.67, is_arret_maladie=True))
    alertes = _r08(bulletin)
    assert len(alertes) == 1
    assert alertes[0].message == (
        "Heures travaillées (0.00 h) inférieures à 50 % du volume contractuel (151.67 h)."
    )


def test_des_absences_non_remunerees_comptent_comme_non_travaillees():
    bulletin = _bulletin(
        _base(),
        _retenue("Absence maladie du 01/10 au 16/10", 84.0, is_arret_maladie=True),
        _retenue("Absence non rémunérée du 19/10/26", 7.0),
    )
    alertes = _r08(bulletin)
    assert len(alertes) == 1
    assert alertes[0].value_n == 60.67
