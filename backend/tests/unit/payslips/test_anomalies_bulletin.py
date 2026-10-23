"""Règles B : un bulletin se relit depuis ses propres lignes, au centime.

Aucun bulletin réel. Les montants sont choisis pour que base × taux tombe juste,
puis décalés d'un ou deux centimes.
"""

from __future__ import annotations

import pytest

from app.modules.payslips.domain.anomalies_bulletin import anomalies_du_bulletin

pytestmark = pytest.mark.unit


def _bulletin() -> dict:
    return {
        "salaire_brut": 2000.0,
        "calcul_du_brut": [
            {"libelle": "Salaire de base", "gain": 1800.0, "perte": None},
        ],
        "details_conges": [
            {"libelle": "Indemnité de congés payés", "gain": 200.0, "perte": None},
        ],
        "details_absences": [],
        "cotisations_officielles": [
            {
                "code": "sante",
                "libelle": "Santé",
                "lignes": [
                    {
                        "libelle": "Maladie",
                        "base": 2000.0,
                        "taux_salarial": 0.0,
                        "montant_salarial": 0.0,
                        "taux_patronal": 0.07,
                        "montant_patronal": 140.0,
                    }
                ],
                "total_salarial": 0.0,
                "total_patronal": 140.0,
            }
        ],
        "structure_cotisations": {"total_salarial": 0.0, "total_patronal": 140.0},
    }


def _ids(bulletin: dict) -> set[str]:
    return {alerte.rule_id for alerte in anomalies_du_bulletin(bulletin)}


def test_un_bulletin_coherent_ne_leve_rien():
    assert anomalies_du_bulletin(_bulletin()) == []


def test_un_centime_sur_une_cotisation_ne_leve_pas():
    bulletin = _bulletin()
    bulletin["cotisations_officielles"][0]["lignes"][0]["montant_patronal"] = 140.01
    bulletin["cotisations_officielles"][0]["total_patronal"] = 140.01
    bulletin["structure_cotisations"]["total_patronal"] = 140.01
    assert "B01" not in _ids(bulletin)


def test_deux_centimes_sur_une_cotisation_levent_la_ligne():
    bulletin = _bulletin()
    bulletin["cotisations_officielles"][0]["lignes"][0]["montant_patronal"] = 140.02
    bulletin["cotisations_officielles"][0]["total_patronal"] = 140.02
    bulletin["structure_cotisations"]["total_patronal"] = 140.02
    alertes = anomalies_du_bulletin(bulletin)
    assert len(alertes) == 1
    alerte = alertes[0]
    assert alerte.rule_id == "B01"
    assert alerte.level == "CRITIQUE"
    assert alerte.value_n == 140.02
    assert alerte.value_n1 == 140.0
    assert alerte.delta_eur == 0.02
    assert "Maladie" in alerte.message
    assert "140,02" in alerte.message
    assert "140,00" in alerte.message


def test_une_ligne_sans_taux_n_est_pas_rejouee_par_un_produit():
    bulletin = _bulletin()
    bulletin["cotisations_officielles"][0]["lignes"].append(
        {
            "libelle": "Mutuelle",
            "base": 1.0,
            "taux_salarial": None,
            "montant_salarial": 17.62,
            "taux_patronal": None,
            "montant_patronal": 17.62,
        }
    )
    bulletin["structure_cotisations"]["total_salarial"] = 17.62
    bulletin["structure_cotisations"]["total_patronal"] = 157.62
    bulletin["cotisations_officielles"][0]["total_salarial"] = 17.62
    bulletin["cotisations_officielles"][0]["total_patronal"] = 157.62
    assert anomalies_du_bulletin(bulletin) == []


def test_la_reduction_generale_n_est_pas_un_taux_du_mois():
    """Le taux stocké est le coefficient annuel. Le montant du mois ne s'y multiplie pas."""
    bulletin = _bulletin()
    bulletin["cotisations_officielles"][0]["lignes"].append(
        {
            "coti_id": "reduction_generale",
            "libelle": "Réduction générale de cotisations patronales",
            "base": 2000.0,
            "taux_salarial": None,
            "montant_salarial": 0.0,
            "taux_patronal": 0.225195,
            "montant_patronal": -450.39,
        }
    )
    bulletin["structure_cotisations"]["total_patronal"] = 140.0 - 450.39
    bulletin["cotisations_officielles"][0]["total_patronal"] = 140.0 - 450.39
    assert anomalies_du_bulletin(bulletin) == []


def test_une_mutuelle_au_forfait_n_est_pas_rejouee_par_son_taux_affiche():
    """Un ancien bulletin met le forfait en base et affiche 1 %. Ce n'est pas le calcul."""
    bulletin = _bulletin()
    bulletin["cotisations_officielles"][0]["lignes"].append(
        {
            "coti_id": "mutuelle",
            "libelle": "Mutuelle",
            "base": 29.24,
            "taux_salarial": 0.01,
            "montant_salarial": 29.24,
            "taux_patronal": None,
            "montant_patronal": 29.23,
        }
    )
    bulletin["structure_cotisations"]["total_salarial"] = 29.24
    bulletin["structure_cotisations"]["total_patronal"] = 169.23
    bulletin["cotisations_officielles"][0]["total_salarial"] = 29.24
    bulletin["cotisations_officielles"][0]["total_patronal"] = 169.23
    assert anomalies_du_bulletin(bulletin) == []


def test_un_centime_sur_le_brut_ne_leve_pas():
    bulletin = _bulletin()
    bulletin["salaire_brut"] = 2000.01
    assert "B02" not in _ids(bulletin)


def test_deux_centimes_sur_le_brut_levent_la_somme():
    bulletin = _bulletin()
    bulletin["salaire_brut"] = 2000.02
    alertes = [a for a in anomalies_du_bulletin(bulletin) if a.rule_id == "B02"]
    assert len(alertes) == 1
    assert alertes[0].value_n == 2000.02
    assert alertes[0].value_n1 == 2000.0
    assert alertes[0].level == "CRITIQUE"


def test_un_sous_total_de_brut_ne_compte_pas_deux_fois():
    bulletin = _bulletin()
    bulletin["calcul_du_brut"].append(
        {"libelle": "Total", "gain": 1800.0, "perte": None, "is_sous_total": True}
    )
    assert anomalies_du_bulletin(bulletin) == []


def test_le_total_salarial_imprime_suit_la_somme_des_lignes():
    bulletin = _bulletin()
    bulletin["structure_cotisations"]["total_salarial"] = 0.02
    alertes = [a for a in anomalies_du_bulletin(bulletin) if a.rule_id == "B03"]
    assert len(alertes) == 1
    assert alertes[0].value_n == 0.02
    assert alertes[0].value_n1 == 0.0


def test_un_bulletin_ancien_se_relit_depuis_les_blocs():
    """Sans rubriques officielles, les lignes sont dans la structure. Les sous-totaux ne comptent pas."""
    bulletin = {
        "salaire_brut": 1000.0,
        "calcul_du_brut": [{"libelle": "Salaire de base", "gain": 1000.0}],
        "structure_cotisations": {
            "bloc_principales": [
                {
                    "libelle": "Maladie",
                    "base": 1000.0,
                    "taux_salarial": 0.0,
                    "montant_salarial": 0.0,
                    "taux_patronal": 0.07,
                    "montant_patronal": 70.0,
                }
            ],
            "bloc_autres_contributions": {
                "lignes": [
                    {
                        "libelle": "Autres",
                        "montant_salarial": 0.0,
                        "montant_patronal": 12.0,
                        "taux_patronal": None,
                    }
                ],
                "total": 12.0,
            },
            "total_avant_csg_crds": {
                "libelle": "Total",
                "montant_salarial": 0.0,
                "montant_patronal": 70.0,
            },
            "total_salarial": 0.0,
            "total_patronal": 82.0,
        },
    }
    assert anomalies_du_bulletin(bulletin) == []
    bulletin["structure_cotisations"]["total_patronal"] = 82.02
    alertes = anomalies_du_bulletin(bulletin)
    assert [alerte.rule_id for alerte in alertes] == ["B04"]


def test_deux_rangements_divergents_ne_font_pas_un_total_faux():
    """Le total stocké suit les blocs. Les rubriques officielles sont un autre rangement."""
    bulletin = _bulletin()
    bulletin["structure_cotisations"] = {
        "bloc_principales": [
            {"montant_salarial": 0.0, "montant_patronal": 140.0},
        ],
        "total_salarial": 0.0,
        "total_patronal": 140.0,
    }
    ligne = bulletin["cotisations_officielles"][0]["lignes"][0]
    ligne["taux_patronal"] = None
    ligne["montant_patronal"] = 110.0
    bulletin["cotisations_officielles"][0]["total_patronal"] = 110.0
    assert anomalies_du_bulletin(bulletin) == []


def test_un_total_de_rubrique_suit_ses_lignes():
    bulletin = _bulletin()
    bulletin["cotisations_officielles"][0]["total_patronal"] = 140.02
    alertes = anomalies_du_bulletin(bulletin)
    assert [alerte.rule_id for alerte in alertes] == ["B04"]
    assert "Santé" in alertes[0].message
    assert alertes[0].delta_eur == 0.02


def test_le_total_patronal_imprime_suit_la_somme_des_lignes():
    bulletin = _bulletin()
    bulletin["structure_cotisations"]["total_patronal"] = 139.98
    alertes = [a for a in anomalies_du_bulletin(bulletin) if a.rule_id == "B04"]
    assert len(alertes) == 1
    assert alertes[0].value_n == 139.98
    assert alertes[0].value_n1 == 140.0
    assert alertes[0].delta_eur == -0.02
