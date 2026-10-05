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


def test_absence_injustifiee_hors_salaire_retabli_mais_dans_la_remuneration_habituelle():
    """L'ancien logiciel (juin) : 003 = 001 malgré trois absences injustifiées,
    029 les réintègre (1 934,45 + 3 × 90,68 + 38,86 = 2 245,35)."""
    bulletin = copy.deepcopy(BULLETIN)
    bulletin["salaire_brut"] = 1934.45
    bulletin["calcul_du_brut"] = [
        {"libelle": "Salaire de base", "quantite": 151.67, "taux": 12.954, "gain": 1964.73},
        {"libelle": "Heures suppl. structurelles majorées à 25%", "quantite": 17.33, "taux": 16.1925, "gain": 280.62},
        {"libelle": "Abs. Abs injustifiée 040626", "quantite": 7.0, "perte": 90.68},
        {"libelle": "Abs. Abs injustifiée 110626", "quantite": 7.0, "perte": 90.68},
        {"libelle": "Abs. Abs injustifiée 150626", "quantite": 7.0, "perte": 90.68},
        {"libelle": "Réduction HS structurelles (jours d'absence)", "quantite": 2.4, "perte": 38.86},
    ]
    remunerations = _remunerations(_lignes(bulletin=bulletin))
    assert remunerations["003"] == "1934.45"
    assert remunerations["029"] == "2245.35"


def _blocs_54(lignes) -> List[Tuple[str, str, str, str]]:
    sortie = []
    for rubrique, valeur in lignes:
        if rubrique == "S21.G00.54.001":
            sortie.append([valeur])
        elif rubrique.startswith("S21.G00.54.") and rubrique[-3:] in ("002", "003", "004"):
            sortie[-1].append(valeur)
    return [tuple(b) for b in sortie]


def test_participation_calculee_en_54_types_11_et_37():
    """Participation 2025 versée en mai 2026 : 11 (participation) et 37 (versée
    directement par l'employeur), son montant brut, l'exercice 2025 — même si
    un acompte a déjà été versé (ancien logiciel, mai 2026)."""
    bulletin = copy.deepcopy(BULLETIN)
    bulletin["participations"] = [
        {"brut": 3936.59, "part_pee": 0.0, "libelle": "Participation 2025 — numéraire"}
    ]
    bulletin["primes_non_soumises"] = [
        {"libelle": "Acompte participation 2025 (déjà versé)", "montant": -1000.0}
    ]
    blocs = [b for b in _blocs_54(_lignes(bulletin=bulletin, periode="2026-05")) if b[0] in ("11", "37")]
    assert blocs == [
        ("11", "3936.59", "01012025", "31122025"),
        ("37", "3936.59", "01012025", "31122025"),
    ]


def test_participation_placee_n_est_pas_versee_directement():
    bulletin = copy.deepcopy(BULLETIN)
    bulletin["participations"] = [{"brut": 1000.0, "part_pee": 400.0, "libelle": "Participation 2025"}]
    blocs = {b[0]: b[1] for b in _blocs_54(_lignes(bulletin=bulletin, periode="2026-05"))}
    assert blocs["11"] == "1000.00"
    assert blocs["37"] == "600.00"


def test_participation_d_un_bulletin_repris_lue_dans_les_elements_non_soumis():
    bulletin = copy.deepcopy(BULLETIN)
    bulletin["primes_non_soumises"] = [
        {"libelle": "Participation 2025", "montant": 1752.57},
        {"libelle": "Acompte sur participation 2025", "montant": -500.0},
    ]
    blocs = [b for b in _blocs_54(_lignes(bulletin=bulletin, periode="2026-05")) if b[0] in ("11", "37")]
    assert [b[:2] for b in blocs] == [("11", "1752.57"), ("37", "1752.57")]


def _blocs_52(lignes) -> List[Tuple[str, str]]:
    sortie = []
    for rubrique, valeur in lignes:
        if rubrique == "S21.G00.52.001":
            sortie.append([valeur])
        elif rubrique == "S21.G00.52.002":
            sortie[-1].append(valeur)
    return [tuple(b) for b in sortie]


def test_prime_de_partage_de_la_valeur_exoneree_en_52_904():
    """Moins de 50 salariés : PPV exonérée et non imposable, hors brut (CT 52.001 = 904)."""
    bulletin = copy.deepcopy(BULLETIN)
    bulletin["primes_non_soumises"] = [
        {"libelle": "Prime de partage de la valeur (PPV)", "montant": 100.0, "prime_id": "prime_partage_valeur"},
        {"libelle": "Prime de transport (carburant / frais de trajet)", "montant": 100.0, "prime_id": "prime_transport"},
    ]
    assert _blocs_52(_lignes(bulletin=bulletin, periode="2026-09")) == [("904", "100.00")]


def test_prime_de_partage_de_la_valeur_imposable_en_52_905():
    """50 salariés et plus : exonérée socialement mais imposable (905)."""
    bulletin = copy.deepcopy(BULLETIN)
    bulletin["revenus_hors_brut_imposables"] = [
        {"libelle": "Prime de partage de la valeur (PPV)", "montant": 250.0, "prime_id": "prime_partage_valeur"}
    ]
    assert _blocs_52(_lignes(bulletin=bulletin, periode="2026-09")) == [("905", "250.00")]


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
