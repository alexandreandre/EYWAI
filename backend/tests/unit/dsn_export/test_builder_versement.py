"""Versement (bloc 50) et ses enfants : net versé, activité, revenus en net,
autres éléments de revenu, salaire rétabli, SMIC de la réduction générale.

Données inventées, mais aux montants d'un salarié réel de juin 2026 dont la
DSN de l'ancien logiciel fait référence : chaque attendu y a été lu.
"""

from __future__ import annotations

import copy
from typing import Dict, List, Tuple

from app.modules.dsn_export.application.builder import build_parsed_dsn_from_payroll
from app.modules.dsn_export.domain.writer import encode_dsn_bytes

SOCIETE = {
    "siret": "12345678900011",
    "name": "Société d'essai",
    "address": {"rue": "1 rue de l'Essai", "code_postal": "01000", "ville": "BOURG EN BRESSE"},
    "code_naf": "2229A",
    "urssaf_number": "79484650100011",
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
        "dispositif_politique_publique": "99",
    },
}

BULLETIN = {
    "salaire_brut": 3855.98,
    "net_a_payer": 2981.94,
    "synthese_net": {
        "net_imposable": 2668.56,
        "montant_net_social": 3194.81,
        "montant_net_hs_exonerees": 419.51,
        "impot_prelevement_a_la_source": {"base": 2668.56, "taux": 4.3, "montant": 114.75},
    },
    "calcul_du_brut": [
        {"libelle": "Salaire de base", "quantite": 151.67, "gain": 3147.46},
        {"libelle": "Heures suppl. structurelles majorées à 25%", "quantite": 17.33, "gain": 449.54},
        {"libelle": "SOUS-TOTAL SALAIRE CONTRACTUEL", "quantite": 169.0, "gain": 3597.0, "is_sous_total": True},
        {"libelle": "Prime ancienneté", "quantite": 2877.6, "gain": 258.98},
    ],
    "primes_non_soumises": [{"libelle": "Indemnité de transport", "montant": 250.0}],
    "structure_cotisations": {
        "bloc_principales": [
            {"coti_id": "csg_deductible", "base": 3490.39, "taux_salarial": 0.068, "montant_salarial": 237.35},
            {"coti_id": "mutuelle", "libelle": "Mutuelle isolé", "montant_salarial": 29.24, "montant_patronal": 29.23},
            {"coti_id": "mutuelle", "libelle": "Mutuelle famille (option)", "montant_salarial": 98.13, "montant_patronal": 0.0},
            {
                "coti_id": "prevoyance_cadre",
                "base": 3855.98,
                "taux_salarial": 0.00465,
                "montant_salarial": 17.93,
                "taux_patronal": 0.00465,
                "montant_patronal": 17.93,
            },
            {
                "coti_id": "retraite_sup",
                "base": 3855.98,
                "taux_salarial": 0.025,
                "montant_salarial": 96.4,
                "taux_patronal": 0.025,
                "montant_patronal": 96.4,
            },
        ],
        "bloc_csg_non_deductible": [
            {"coti_id": "csg_non_deductible", "base": 3490.39, "taux_salarial": 0.029, "montant_salarial": 101.22},
            {"coti_id": "csg_non_deductible", "base": 441.67, "taux_salarial": 0.097, "montant_salarial": 42.84},
        ],
        "bloc_allegements": [
            {
                "coti_id": "reduction_generale",
                "base": 3855.98,
                "montant_patronal": -263.27,
                "smic_reference_mois": 2031.38,
            }
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
    lignes = []
    for brute in texte.splitlines():
        rubrique, valeur = brute.split(",", 1)
        lignes.append((rubrique, valeur.strip("'")))
    return lignes


def _valeur(lignes, rubrique: str) -> str:
    return next(v for r, v in lignes if r == rubrique)


def _blocs(lignes, bloc: str) -> List[Dict[str, str]]:
    """Instances successives d'un bloc, rubriques regroupées."""
    sortie: List[Dict[str, str]] = []
    precedent = None
    for rubrique, valeur in lignes:
        if not rubrique.startswith(bloc + "."):
            precedent = None
            continue
        numero = rubrique.rsplit(".", 1)[1]
        if precedent is None or numero <= precedent:
            sortie.append({})
        sortie[-1][numero] = valeur
        precedent = numero
    return sortie


# --------------------------------------------------------------------------
# Montant net versé (S21.G00.50.004)
# --------------------------------------------------------------------------


def test_net_verse_part_de_la_remuneration_nette_fiscale():
    """CT 2026 : RNF - CSG non déductible - CRDS - part patronale santé.

    2668,56 - (101,22 + 12,81) - 29,23 = 2525,30. Le net à payer (2981,94)
    n'est pas le net versé : ni l'impôt, ni les heures sup exonérées, ni
    l'indemnité de transport n'y entrent.
    """
    assert _valeur(_lignes(), "S21.G00.50.004") == "2525.30"


def test_net_verse_ignore_un_acompte_ou_un_pret():
    """L'acompte et le remboursement de prêt changent le net payé, pas le net versé."""
    bulletin = copy.deepcopy(BULLETIN)
    bulletin["net_a_payer"] = 1981.94
    bulletin["synthese_net"]["acompte_verse"] = 800.0
    bulletin["remboursements_prets"] = {"total_rembourse": 200.0}
    assert _valeur(_lignes(bulletin=bulletin), "S21.G00.50.004") == "2525.30"


# --------------------------------------------------------------------------
# Éléments de revenu calculés en net (S21.G00.58)
# --------------------------------------------------------------------------


def test_heures_sup_exonerees_en_58_type_01_avant_le_net_social():
    blocs = _blocs(_lignes(), "S21.G00.58")
    assert [(b["003"], b["004"]) for b in blocs] == [("01", "419.51"), ("03", "3194.81")]


def test_pas_de_58_type_01_sans_heures_sup_exonerees():
    bulletin = copy.deepcopy(BULLETIN)
    bulletin["synthese_net"]["montant_net_hs_exonerees"] = 0.0
    assert [b["003"] for b in _blocs(_lignes(bulletin=bulletin), "S21.G00.58")] == ["03"]


# --------------------------------------------------------------------------
# Autres éléments de revenu brut (S21.G00.54)
# --------------------------------------------------------------------------


def test_parts_patronales_sante_en_92_prevoyance_et_retraite_sup_en_93():
    blocs = _blocs(_lignes(), "S21.G00.54")
    assert [(b["001"], b["002"], b["003"], b["004"]) for b in blocs] == [
        ("92", "29.23", "01062026", "30062026"),
        ("93", "114.33", "01062026", "30062026"),
    ]


# --------------------------------------------------------------------------
# Activité (S21.G00.53)
# --------------------------------------------------------------------------


def _activites(lignes) -> List[Tuple[str, str, str, str]]:
    """(type de rémunération parent, type, mesure, unité)."""
    sortie = []
    parent = ""
    courant = None
    for rubrique, valeur in lignes:
        if rubrique == "S21.G00.51.011":
            parent = valeur
        if rubrique == "S21.G00.53.001":
            courant = [parent, valeur, "", ""]
            sortie.append(courant)
        elif rubrique == "S21.G00.53.002" and courant:
            courant[2] = valeur
        elif rubrique == "S21.G00.53.003" and courant:
            courant[3] = valeur
    return [tuple(a) for a in sortie]


def test_les_heures_sont_rattachees_au_salaire_chomage_les_jours_au_brut():
    """CCH-11 / CCH-12 : unité 40 sous la 001, toute autre mesure sous la 002."""
    assert _activites(_lignes()) == [("001", "01", "30.00", "40"), ("002", "01", "169.00", "")]


def test_absence_non_payee_en_heures_d_absence_de_type_02():
    """160,50 h payées et 8,50 h d'absence (7,63 + 0,87 de HS structurelles)."""
    bulletin = copy.deepcopy(BULLETIN)
    bulletin["calcul_du_brut"] = [
        {"libelle": "Salaire de base", "quantite": 151.67, "gain": 1867.06},
        {"libelle": "Heures suppl. structurelles majorées à 25%", "quantite": 17.33, "gain": 266.67},
        {"libelle": "SOUS-TOTAL SALAIRE CONTRACTUEL", "quantite": 169.0, "gain": 2133.73, "is_sous_total": True},
        {"libelle": "Abs. Abs aut nonpayé 080626", "quantite": 7.63, "perte": 93.93},
        {"libelle": "Réduction HS structurelles (jours d'absence)", "quantite": 0.87, "perte": 13.39},
    ]
    bulletin["salaire_brut"] = 2026.41
    activites = _activites(_lignes(bulletin=bulletin))
    assert ("002", "01", "160.50", "") in activites
    assert ("002", "02", "8.50", "") in activites


def test_conges_payes_ne_sont_pas_une_absence_entree_sortie_pas_une_absence_02():
    """CP payés et absence pour entrée ou sortie : pas d'heures d'absence (02).

    Les CP restent du travail rémunéré ; l'absence d'entrée réduit les heures
    payées sans être une absence du salarié. L'accident du travail (28 h + 4,8 h
    de HS structurelles) est, lui, une durée d'absence.
    """
    bulletin = copy.deepcopy(BULLETIN)
    bulletin["calcul_du_brut"] = [
        {"libelle": "H.Absence Congés Payés", "quantite": 7.0, "perte": 85.4},
        {"libelle": "Réduction HS structurelles (jours d'absence)", "quantite": 0.8, "perte": 12.2},
        {"libelle": "Salaire de base", "quantite": 151.67, "gain": 1850.37},
        {"libelle": "Heures suppl. structurelles majorées à 25%", "quantite": 17.33, "gain": 264.28},
        {"libelle": "Absence pour entrée ou sortie", "quantite": 2.0, "perte": 24.4},
        {"libelle": "Absence A.T. 230526-290526", "quantite": 28.0, "perte": 341.6},
        {"libelle": "Réduction HS structurelles (jours d'absence)", "quantite": 4.8, "perte": 73.2},
        {"libelle": "ARBITRAGE DES CONGES PAYES", "quantite": 97.6, "gain": 97.6},
    ]
    activites = _activites(_lignes(bulletin=bulletin))
    assert ("002", "01", "134.20", "") in activites  # 169 - 2 - 28 - 4,8
    assert ("002", "02", "32.80", "") in activites


def test_jours_du_plafond_comptes_depuis_l_embauche():
    """Embauché le 07/04 : 24 jours calendaires en avril, pas 30."""
    salarie = {**SALARIE, "hire_date": "2026-04-07", "contract_type": "CDD", "contract_end_date": "2026-09-15"}
    activites = _activites(_lignes(salarie=salarie, periode="2026-04"))
    assert ("001", "01", "24.00", "40") in activites


# --------------------------------------------------------------------------
# Salaire rétabli (003) et rémunération habituelle (029)
# --------------------------------------------------------------------------


def test_salaire_retabli_reintegre_les_retenues_d_absence():
    """2026,41 de brut + 93,93 + 13,39 retenus = 2133,73, le mois sans absence."""
    bulletin = copy.deepcopy(BULLETIN)
    bulletin["calcul_du_brut"] = [
        {"libelle": "Salaire de base", "quantite": 151.67, "gain": 1867.06},
        {"libelle": "Heures suppl. structurelles majorées à 25%", "quantite": 17.33, "gain": 266.67},
        {"libelle": "SOUS-TOTAL SALAIRE CONTRACTUEL", "quantite": 169.0, "gain": 2133.73, "is_sous_total": True},
        {"libelle": "Abs. Abs aut nonpayé 080626", "quantite": 7.63, "perte": 93.93},
        {"libelle": "Réduction HS structurelles (jours d'absence)", "quantite": 0.87, "perte": 13.39},
    ]
    bulletin["salaire_brut"] = 2026.41
    remunerations = {b["011"]: b["013"] for b in _blocs(_lignes(bulletin=bulletin), "S21.G00.51")}
    assert remunerations["003"] == "2133.73"
    assert remunerations["029"] == "2133.73"
    assert remunerations["001"] == "2026.41"


def test_salaire_retabli_deduit_le_maintien_verse_pendant_l_arret():
    """Le maintien compense l'absence : il sort du salaire rétabli."""
    bulletin = copy.deepcopy(BULLETIN)
    bulletin["calcul_du_brut"] = [
        {"libelle": "Salaire de base", "quantite": 151.67, "gain": 2000.0},
        {"libelle": "Absence maladie 160326-280326", "quantite": 70.0, "perte": 900.0},
        {"libelle": "Maintien de salaire", "quantite": 300.0, "gain": 300.0},
    ]
    bulletin["salaire_brut"] = 1400.0
    remunerations = {b["011"]: b["013"] for b in _blocs(_lignes(bulletin=bulletin), "S21.G00.51")}
    assert remunerations["003"] == "2000.00"


# --------------------------------------------------------------------------
# SMIC retenu pour la réduction générale (S21.G00.79 type 01)
# --------------------------------------------------------------------------


def test_smic_de_la_reduction_generale_lu_sur_la_ligne_du_bulletin():
    """CCH-17 : 018 / 106 exigent le composant 01 sous la base 03."""
    lignes = _lignes()
    composants = []
    base = None
    for rubrique, valeur in lignes:
        if rubrique == "S21.G00.78.001":
            base = valeur
        if rubrique == "S21.G00.79.001":
            composants.append([base, valeur])
        if rubrique == "S21.G00.79.004":
            composants[-1].append(valeur)
    assert ["03", "01", "2031.38"] in composants


def test_smic_nul_d_un_mois_sans_heure_payee_reste_declare():
    """Arrêt tout le mois : la réduction se régularise sur zéro heure ; le SMIC
    retenu vaut 0,00 et se déclare quand même (CCH-17)."""
    bulletin = copy.deepcopy(BULLETIN)
    bulletin["structure_cotisations"]["bloc_allegements"] = [
        {"coti_id": "reduction_generale", "base": 54.67, "montant_patronal": 12.5, "smic_reference_mois": 0.0}
    ]
    lignes = _lignes(bulletin=bulletin)
    composants = [
        (lignes[i][1], lignes[i + 1][1])
        for i in range(len(lignes) - 1)
        if lignes[i][0] == "S21.G00.79.001"
    ]
    assert ("01", "0.00") in composants


def test_cotisation_prevoyance_sans_affiliation_signalee():
    """Une base 31 sans bloc 70 est refusée (CCH-11 / CCH-12) : on le dit."""
    _, avertissements = build_parsed_dsn_from_payroll(
        SOCIETE, [{"employee": SALARIE, "payslip_data": BULLETIN}], "2026-06"
    )
    assert any("affiliation" in a.lower() and "177017512345678"[:13] in a for a in avertissements)


def test_montant_soumis_au_pas_nul_quand_la_paie_l_annule():
    """Apprenti sous le seuil : la paie ne soumet rien au PAS (assiette 0) ;
    50.013 vaut 0.00, pas la RNF (l'ancien logiciel : 0.00)."""
    bulletin = copy.deepcopy(BULLETIN)
    bulletin["synthese_net"]["impot_prelevement_a_la_source"] = {"base": 0.0, "taux": 0.0, "montant": 0.0}
    assert _valeur(_lignes(bulletin=bulletin), "S21.G00.50.013") == "0.00"
