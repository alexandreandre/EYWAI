"""Compléments vus au rejeu de juin 2026 contre la DSN de l'ancien logiciel :
composants 79 des parts patronales, indemnités conventionnelles et ICCP,
rémunérations hors éléments non affectés par l'absence, salaire rétabli d'un
mois incomplet, identifiant PAS d'un CDD court, activité au forfait jours.

Données inventées ; attendus lus dans les DSN 2026 de l'ancien logiciel ou
dans le cahier technique NEODeS 2026.
"""

from __future__ import annotations

import copy
from typing import Dict, List, Tuple

from app.modules.dsn_export.application.builder import build_parsed_dsn_from_payroll
from app.modules.dsn_export.domain.evenements import indemnites_de_rupture
from app.modules.dsn_export.domain.writer import encode_dsn_bytes

SOCIETE = {
    "siret": "12345678900011",
    "name": "Société d'essai",
    "address": {"rue": "1 rue de l'Essai", "code_postal": "01000", "ville": "BOURG EN BRESSE"},
    "code_naf": "2229A",
    "taux_at_mp": 3.15,
}

SALARIE = {
    "id": "e1",
    "first_name": "Paul",
    "last_name": "ESSAI",
    "nir": "177017512345678",
    "sexe": "M",
    "date_naissance": "1977-01-01",
    "lieu_naissance": "PARIS (75)",
    "adresse": {"rue": "1 rue du Test", "code_postal": "01000", "ville": "BOURG EN BRESSE"},
    "hire_date": "2014-09-01",
    "contract_type": "CDI",
    "statut": "Cadre",
    "duree_hebdomadaire": 39.0,
    "classification_conventionnelle": {
        "pcs": "628g",
        "idcc": "0292",
        "position": "200",
        "niveau_dsn": "830",
        "classification_dsn": "252HK",
        "taux_at_individuel_dsn": "3.15",
        "code_statut_dsn": "04",
        "numero_contrat_dsn": "00000",
    },
}

BULLETIN = {
    "salaire_brut": 3855.98,
    "synthese_net": {"net_imposable": 2668.56, "montant_net_social": 3194.81},
    "calcul_du_brut": [
        {"libelle": "Salaire de base", "quantite": 151.67, "taux": 20.752, "gain": 3147.46},
        {"libelle": "Heures suppl. structurelles majorées à 25%", "quantite": 17.33, "taux": 25.94, "gain": 449.54},
        {"libelle": "SOUS-TOTAL SALAIRE CONTRACTUEL", "quantite": 169.0, "gain": 3597.0, "is_sous_total": True},
        {"libelle": "Prime ancienneté", "quantite": 2877.6, "gain": 258.98},
    ],
    "structure_cotisations": {
        "bloc_principales": [
            {"coti_id": "mutuelle", "montant_salarial": 29.24, "montant_patronal": 29.23},
            {"coti_id": "prevoyance_cadre", "base": 3855.98, "montant_salarial": 17.93, "montant_patronal": 17.93},
            {"coti_id": "retraite_sup", "base": 3855.98, "montant_salarial": 96.4, "montant_patronal": 96.4},
        ],
        "bloc_allegements": [
            {"coti_id": "reduction_generale", "base": 3855.98, "montant_patronal": -263.27, "smic_reference_mois": 2031.38}
        ],
    },
}


def _lignes(salarie: Dict = None, bulletin: Dict = None, periode: str = "2026-06") -> List[Tuple[str, str]]:
    fichier, _ = build_parsed_dsn_from_payroll(
        SOCIETE,
        [{"employee": salarie or SALARIE, "payslip_data": bulletin or BULLETIN}],
        periode,
    )
    texte = encode_dsn_bytes(fichier).decode("iso-8859-15")
    return [(l.split(",", 1)[0], l.split(",", 1)[1].strip("'")) for l in texte.splitlines()]


def _remunerations(lignes) -> Dict[str, str]:
    sortie: Dict[str, str] = {}
    type_courant = None
    for rubrique, valeur in lignes:
        if rubrique == "S21.G00.51.011":
            type_courant = valeur
        elif rubrique == "S21.G00.51.013" and type_courant:
            sortie[type_courant] = valeur
    return sortie


def _composants_base_03(lignes) -> List[Tuple[str, str]]:
    sortie = []
    base = None
    for rubrique, valeur in lignes:
        if rubrique == "S21.G00.78.001":
            base = valeur
        elif rubrique == "S21.G00.79.001" and base == "03":
            sortie.append([valeur])
        elif rubrique == "S21.G00.79.004" and base == "03":
            sortie[-1].append(valeur)
    return [tuple(c) for c in sortie]


def test_composants_des_parts_patronales_sante_et_retraite_supplementaire():
    """79.04 = part patronale santé, 79.05 = retraite supplémentaire, sous la
    base 03 (146 salariés-mois sur 146 chez l'ancien logiciel)."""
    assert _composants_base_03(_lignes()) == [
        ("01", "2031.38"),
        ("04", "29.23"),
        ("05", "96.40"),
    ]


def test_indemnite_conventionnelle_de_depart_et_iccp_au_depart():
    bulletin = {
        "calcul_du_brut": [
            {"libelle": "Indemnités de CP", "gain": 223.04},
            {"libelle": "Ind.Conv départ en retraite", "gain": 12712.27},
            {"libelle": "Indemnité CP", "gain": 3643.2},
        ]
    }
    assert indemnites_de_rupture(bulletin, sortie=True) == [
        ("006", 12712.27, True),
        ("020", 3643.2, True),
    ]


def test_hors_depart_les_indemnites_de_cp_ne_sont_pas_une_iccp():
    bulletin = {"calcul_du_brut": [{"libelle": "Indemnité CP", "gain": 100.0}]}
    assert indemnites_de_rupture(bulletin, sortie=False) == []


def test_sans_absence_028_et_029_suivent_001_et_003():
    """L'ancien logiciel ne retire heures sup et indemnités qu'un mois d'absence :
    départ à la retraite sans absence, 028 = 001 = 19 061,68."""
    salarie = {
        **SALARIE,
        "sortie_dsn": {"exit_type": "depart_retraite", "last_working_day": "2026-06-30"},
    }
    bulletin = copy.deepcopy(BULLETIN)
    bulletin["calcul_du_brut"].append({"libelle": "Ind.Conv départ en retraite", "gain": 12712.27})
    bulletin["salaire_brut"] = 3855.98 + 12712.27
    remunerations = _remunerations(_lignes(salarie, bulletin))
    assert remunerations["002"] == "3855.98"
    assert remunerations["028"] == "16568.25"
    assert remunerations["029"] == "16568.25"


def test_salaire_retabli_d_un_mois_d_entree_reconstitue_le_mois_complet():
    """Entré le 22/06 : 49 h de base et 5,60 h de HS payées ; le rétabli est le
    mois complet, 151,67 h × 12,31 + 17,33 h × 15,3875 = 2133,73."""
    salarie = {**SALARIE, "hire_date": "2026-06-22", "contract_type": "CDI"}
    bulletin = copy.deepcopy(BULLETIN)
    bulletin["salaire_brut"] = 689.36
    bulletin["calcul_du_brut"] = [
        {"libelle": "Salaire de base", "quantite": 49.0, "taux": 12.31, "gain": 603.19},
        {"libelle": "Heures suppl. structurelles majorées à 25%", "quantite": 5.6, "taux": 15.3875, "gain": 86.17},
    ]
    remunerations = _remunerations(_lignes(salarie, bulletin))
    assert remunerations["003"] == "2133.73"
    assert remunerations["001"] == "689.36"


def test_cdd_a_terme_imprecis_sans_taux_dgfip_porte_l_identifiant_moins_un():
    """CT 50.008 : CDD de deux mois au plus ou à terme imprécis → « -1 »."""
    salarie = {
        **SALARIE,
        "hire_date": "2026-06-22",
        "contract_type": "CDD",
        "contract_end_date": "2026-08-14",
        "pas_type_taux": "13",
    }
    lignes = _lignes(salarie)
    assert ("S21.G00.50.007", "13") in lignes
    assert ("S21.G00.50.008", "-1") in lignes


def test_forfait_jours_declare_des_jours_d_activite():
    """Au forfait, la mesure est en jours (40.011 = 20) : 22 jours ouvrés en juin."""
    salarie = {**SALARIE, "is_forfait_jour": True}
    bulletin = copy.deepcopy(BULLETIN)
    bulletin["calcul_du_brut"] = [{"libelle": "Salaire de base", "quantite": None, "gain": 3750.0}]
    bulletin["salaire_brut"] = 3750.0
    lignes = _lignes(salarie, bulletin)
    mesures = [v for r, v in lignes if r == "S21.G00.53.002"]
    assert mesures == ["30.00", "22.00"]
