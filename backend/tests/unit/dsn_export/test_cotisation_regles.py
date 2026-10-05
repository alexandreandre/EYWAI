"""Règles de traduction bulletin → DSN, figées une par une.

Chaque test correspond à une règle lue dans les DSN réellement déposées par le
cabinet, et pour la plupart à une erreur qui a existé. Ils tournent sans
`data/` : ce sont eux qui protègent la CI, le diff de conformité complet ne
tournant qu'en local (`scripts/dsn_cotisations_ecart.py`).
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from app.modules.dsn_export.domain.cotisation_mapping import (
    build_bases_and_cotisations,
    resolve_dsn_cotisation_code,
)
from app.modules.dsn_export.domain.nomenclature_cotisation import libelle_cotisation

PERIODE = ("01052026", "31052026")


def _construire(lignes: List[Dict[str, Any]], brut: float = 3000.0):
    bases, cotisations, avertissements = build_bases_and_cotisations(
        lignes,
        brut=brut,
        period_start=PERIODE[0],
        period_end=PERIODE[1],
    )
    return bases, cotisations, avertissements


def _par_code(cotisations) -> Dict[str, Tuple[str, float, float]]:
    """{code: (base, montant, taux en %)}."""
    resultat: Dict[str, Tuple[str, float, float]] = {}
    for cotisation in cotisations:
        rubriques = cotisation.rubriques
        resultat[cotisation.code] = (
            rubriques["_base"],
            float(rubriques["S21.G00.81.004"]),
            float(rubriques.get("S21.G00.81.007") or 0),
        )
    return resultat


# --------------------------------------------------------------------------
# Découpages : une rubrique de bulletin, deux codes DSN
# --------------------------------------------------------------------------


def test_maladie_a_13_pourcent_se_declare_en_075_plus_907():
    """Au-delà de 2,5 SMIC, seuls 7 % vont en 075 ; le reste est un complément."""
    _, cotisations, _ = _construire(
        [
            {
                "coti_id": "securite_sociale_maladie",
                "libelle": "Sécurité sociale - Maladie",
                "base": 3000.0,
                "taux_patronal": 0.13,
                "montant_patronal": 390.0,
            }
        ]
    )
    codes = _par_code(cotisations)
    assert codes["075"] == ("03", 210.0, 7.0)
    assert codes["907"] == ("03", 180.0, 6.0)
    assert libelle_cotisation("907") == "Complément de cotisation Assurance Maladie"


def test_maladie_a_7_pourcent_ne_produit_pas_de_complement():
    _, cotisations, _ = _construire(
        [
            {
                "coti_id": "securite_sociale_maladie",
                "base": 3000.0,
                "taux_patronal": 0.07,
                "montant_patronal": 210.0,
            }
        ]
    )
    codes = _par_code(cotisations)
    assert "907" not in codes
    assert codes["075"][1] == 210.0


def test_allocations_familiales_majorees_se_declarent_en_074_plus_102():
    _, cotisations, _ = _construire(
        [
            {
                "coti_id": "allocations_familiales",
                "base": 3000.0,
                "taux_patronal": 0.0525,
                "montant_patronal": 157.5,
            }
        ]
    )
    codes = _par_code(cotisations)
    assert codes["074"] == ("03", 103.5, 3.45)
    assert codes["102"] == ("03", 54.0, 1.8)


def test_les_deux_parts_du_decoupage_se_calculent_depuis_l_assiette():
    """Ni l'une ni l'autre n'est un reste : chacune s'arrondit pour son compte.

    Déduire le complément par soustraction décale les deux lignes d'un centime
    dès que le montant du bulletin n'est pas exactement l'assiette multipliée
    par le taux. C'est ce qui faisait diverger 78 salariés.
    """
    _, cotisations, _ = _construire(
        [
            {
                "coti_id": "allocations_familiales",
                "base": 2952.34,
                "taux_patronal": 0.0525,
                # Montant volontairement décalé d'un centime.
                "montant_patronal": 155.00,
            }
        ]
    )
    codes = _par_code(cotisations)
    assert codes["074"][1] == 101.86  # 2952.34 × 3,45 %
    assert codes["102"][1] == 53.14  # 2952.34 × 1,80 %


def test_reduction_generale_se_ventile_entre_018_et_106():
    """La part retraite complémentaire vaut 6,01 / T, T = 39,81 % sous 50 salariés."""
    _, cotisations, _ = _construire(
        [
            {"coti_id": "fnal", "base": 3000.0, "taux_patronal": 0.001, "montant_patronal": 3.0},
            {
                "coti_id": "reduction_generale",
                "base": 3000.0,
                "taux_patronal": 0.1533,
                "montant_patronal": -400.0,
            },
        ]
    )
    codes = _par_code(cotisations)
    part_retraite = round(-400.0 * 0.0601 / 0.3981, 2)
    assert codes["106"][1] == part_retraite
    assert codes["018"][1] == round(-400.0 - part_retraite, 2)
    assert round(codes["018"][1] + codes["106"][1], 2) == -400.0


def test_le_coefficient_maximal_suit_le_taux_de_fnal():
    """FNAL à 0,50 % ⇒ effectif d'au moins 50 ⇒ T = 40,21 %, donc une autre part."""
    _, cotisations, _ = _construire(
        [
            {"coti_id": "fnal", "base": 3000.0, "taux_patronal": 0.005, "montant_patronal": 15.0},
            {
                "coti_id": "reduction_generale",
                "base": 3000.0,
                "montant_patronal": -400.0,
            },
        ]
    )
    codes = _par_code(cotisations)
    assert codes["106"][1] == round(-400.0 * 0.0601 / 0.4021, 2)
    # Et le FNAL déplafonné bascule sur la base 03.
    assert codes["049"][0] == "03"


def test_fnal_plafonne_va_sur_la_base_02():
    _, cotisations, _ = _construire(
        [{"coti_id": "fnal", "base": 3000.0, "taux_patronal": 0.001, "montant_patronal": 3.0}]
    )
    assert _par_code(cotisations)["049"][0] == "02"


# --------------------------------------------------------------------------
# Regroupements : deux rubriques, un seul code
# --------------------------------------------------------------------------


def test_csg_et_crds_se_regroupent_en_072_et_079():
    """Le bulletin sépare déductible et non déductible, la DSN sépare CSG et CRDS."""
    _, cotisations, _ = _construire(
        [
            {
                "coti_id": "csg_deductible",
                "libelle": "CSG déductible",
                "base": 2000.0,
                "taux_salarial": 0.068,
                "montant_salarial": 136.0,
            },
            {
                "coti_id": "csg_non_deductible",
                "libelle": "CSG/CRDS non déductible",
                "base": 2000.0,
                "taux_salarial": 0.029,
                "montant_salarial": 58.0,
            },
        ]
    )
    codes = _par_code(cotisations)
    assert codes["072"] == ("04", 184.0, 9.2)
    assert codes["079"] == ("04", 10.0, 0.5)
    # L'assiette n'est comptée qu'une fois, bien qu'elle porte deux lignes.
    assert len([c for c in cotisations if c.code == "072"]) == 1


def test_la_csg_ne_part_jamais_en_142():
    """142 est la part patronale Agirc-Arrco T1, pas de la CSG.

    Erreur corrigée le 09/08/2026 : toute la CSG salariale gonflait la ligne de
    retraite complémentaire de chaque salarié des sept sociétés.
    """
    assert resolve_dsn_cotisation_code("csg_deductible") != "142"
    assert libelle_cotisation("142").startswith("Cotisation régime unifié Agirc-Arrco")


def test_forfait_social_en_071_et_apec_en_132():
    """093 est la contribution sur indemnités de rupture, pas le forfait social."""
    assert resolve_dsn_cotisation_code("forfait_social") == "071"
    assert resolve_dsn_cotisation_code("apec") == "132"
    assert libelle_cotisation("071") == "Contribution forfait social"
    assert libelle_cotisation("132") == "Cotisation Apec"


# --------------------------------------------------------------------------
# Rattachement aux bases
# --------------------------------------------------------------------------


def test_chaque_cotisation_pointe_sur_une_base_emise():
    _, cotisations, _ = _construire(
        [
            {"coti_id": "ags", "base": 3000.0, "taux_patronal": 0.0025, "montant_patronal": 7.5},
            {
                "coti_id": "versement_mobilite",
                "base": 3000.0,
                "taux_patronal": 0.001,
                "montant_patronal": 3.0,
            },
            {
                "coti_id": "retraite_secu_plafond",
                "base": 3000.0,
                "taux_salarial": 0.069,
                "montant_salarial": 207.0,
                "taux_patronal": 0.0855,
                "montant_patronal": 256.5,
            },
        ]
    )
    codes = _par_code(cotisations)
    assert codes["048"][0] == "07"  # chômage
    assert codes["081"][0] == "57"  # versement mobilité
    assert codes["076"][0] == "02"  # plafonnée


def test_la_cotisation_porte_la_somme_des_deux_parts():
    """La DSN ne connaît pas la distinction salarial / patronal du bulletin."""
    _, cotisations, _ = _construire(
        [
            {
                "coti_id": "retraite_secu_plafond",
                "base": 3000.0,
                "taux_salarial": 0.069,
                "montant_salarial": 207.0,
                "taux_patronal": 0.0855,
                "montant_patronal": 256.5,
            }
        ]
    )
    codes = _par_code(cotisations)
    assert codes["076"][1] == 463.5
    assert codes["076"][2] == 15.45


def test_agirc_arrco_declare_le_total_puis_la_part_patronale():
    """131 porte le total, 142 redéclare la seule part patronale de tranche 1."""
    _, cotisations, _ = _construire(
        [
            {
                "coti_id": "retraite_comp_t1",
                "base": 3000.0,
                "taux_salarial": 0.0315,
                "montant_salarial": 94.5,
                "taux_patronal": 0.0472,
                "montant_patronal": 141.6,
            }
        ]
    )
    codes = _par_code(cotisations)
    assert codes["131"][1] == 236.1
    assert codes["142"][1] == 141.6


def test_le_taux_dsn_est_toujours_positif():
    """Sur une réduction, c'est le montant qui porte le signe, pas le taux."""
    _, cotisations, _ = _construire(
        [
            {
                "coti_id": "reduction_hs_salariale",
                "base": 800.0,
                "taux_salarial": -0.1131,
                "montant_salarial": -90.48,
            }
        ]
    )
    codes = _par_code(cotisations)
    assert codes["114"][1] == -90.48
    assert codes["114"][2] > 0


def test_deduction_heures_sup_prend_la_remuneration_en_assiette():
    """Le bulletin compte des heures, la DSN attend leur rémunération."""
    _, cotisations, _ = _construire(
        [
            {
                "coti_id": "reduction_hs_salariale",
                "base": 333.41,
                "montant_salarial": -37.70,
            },
            {
                "coti_id": "deduction_hs_patronale",
                "base": 15.57,  # heures
                "montant_patronal": -7.79,
            },
        ]
    )
    ligne = next(c for c in cotisations if c.code == "021")
    assert ligne.rubriques["S21.G00.81.003"] == "333.41"
    assert ligne.rubriques["S21.G00.81.004"] == "-7.79"
    # 0,50 € par heure, écrit « 0.500 » dans la rubrique de taux.
    assert ligne.rubriques["S21.G00.81.007"] == "0.500"


def test_solde_de_taxe_d_apprentissage_non_declare_par_salarie():
    _, cotisations, avertissements = _construire(
        [
            {
                "coti_id": "taxe_apprentissage",
                "base": 3000.0,
                "taux_patronal": 0.0059,
                "montant_patronal": 17.7,
            },
            {
                "coti_id": "taxe_apprentissage_solde",
                "base": 3000.0,
                "taux_patronal": 0.0009,
                "montant_patronal": 2.7,
            },
        ]
    )
    codes = _par_code(cotisations)
    assert codes["130"] == ("03", 17.7, 0.59)
    assert not avertissements


# --------------------------------------------------------------------------
# Rejeu de juin 2026 contre la DSN de l'ancien logiciel (04/10/2026)
# --------------------------------------------------------------------------


def _ligne(cotisations, code: str, rang: int = 0):
    return [c for c in cotisations if c.code == code][rang].rubriques


def test_reduction_generale_2026_ventilee_avec_t_a_39_81():
    """RGDU 2026 : T = Tmin 2 % + Tdelta 37,81 % = 39,81 % sous 50 salariés.

    La DSN de juin de l'ancien logiciel ventile 552,97 € en 469,49 (018) et
    83,48 (106) : 552,97 × 6,01 / 39,81. Avec 39,80, on déclarait 83,50.
    """
    _, cotisations, _ = _construire(
        [
            {"coti_id": "fnal", "base": 3084.43, "taux_patronal": 0.001, "montant_patronal": 3.08},
            {"coti_id": "reduction_generale", "base": 3084.43, "montant_patronal": -552.97},
        ],
        brut=3084.43,
    )
    assert _ligne(cotisations, "106")["S21.G00.81.004"] == "-83.48"
    assert _ligne(cotisations, "018")["S21.G00.81.004"] == "-469.49"


def test_reduction_generale_50_salaries_et_plus_t_a_40_21():
    _, cotisations, _ = _construire(
        [
            {"coti_id": "fnal", "base": 3000.0, "taux_patronal": 0.005, "montant_patronal": 15.0},
            {"coti_id": "reduction_generale", "base": 3000.0, "montant_patronal": -400.0},
        ]
    )
    attendu = f"{round(-400.0 * 6.01 / 40.21, 2):.2f}"
    assert _ligne(cotisations, "106")["S21.G00.81.004"] == attendu


def test_reduction_generale_a_pour_assiette_le_brut():
    """CCH-16 : 018 et 106 portent une assiette, la rémunération brute.

    Les bulletins repris rangent le montant de la réduction dans la base de la
    ligne : il ne faut pas la recopier en assiette (on déclarait -552,97).
    """
    _, cotisations, _ = _construire(
        [{"coti_id": "reduction_generale", "base": -552.97, "montant_patronal": -552.97}],
        brut=3084.43,
    )
    assert _ligne(cotisations, "018")["S21.G00.81.003"] == "3084.43"
    assert _ligne(cotisations, "106")["S21.G00.81.003"] == "3084.43"


def test_deux_forfaits_sociaux_a_taux_differents_restent_deux_lignes():
    """8 % sur la prévoyance, 20 % sur la retraite supplémentaire : deux 071.

    Les fusionner donnait un 071 unique à 28 % sur la plus grande assiette.
    La base 05 porte la somme des deux assiettes.
    """
    bases, cotisations, _ = _construire(
        [
            {"coti_id": "forfait_social", "base": 47.16, "taux_patronal": 0.08, "montant_patronal": 3.77},
            {"coti_id": "forfait_social", "base": 96.40, "taux_patronal": 0.20, "montant_patronal": 19.28},
        ]
    )
    lignes_071 = [c.rubriques for c in cotisations if c.code == "071"]
    assert [
        (l["S21.G00.81.003"], l["S21.G00.81.004"], l["S21.G00.81.007"]) for l in lignes_071
    ] == [("47.16", "3.77", "8.000"), ("96.40", "19.28", "20.000")]
    base_05 = next(b for b in bases if b.code == "05")
    assert base_05.rubriques["S21.G00.78.004"] == "143.56"


def test_csg_et_crds_reprennent_les_montants_du_bulletin():
    """072 + 079 = le total CSG/CRDS retenu sur le bulletin, au centime.

    La CRDS (0,50 %) s'arrondit ligne à ligne sur l'assiette des lignes non
    déductibles ; la CSG est le reste. Recalculer 9,20 % de l'assiette totale
    décalait un centime sur un tiers des salariés.
    """
    _, cotisations, _ = _construire(
        [
            {"coti_id": "csg_deductible", "base": 1972.98, "taux_salarial": 0.068, "montant_salarial": 134.16},
            {"coti_id": "csg_non_deductible", "base": 1972.98, "taux_salarial": 0.029, "montant_salarial": 57.21},
            {"coti_id": "csg_non_deductible", "base": 386.03, "taux_salarial": 0.097, "montant_salarial": 37.45},
        ]
    )
    assert _ligne(cotisations, "079")["S21.G00.81.004"] == "11.79"
    assert _ligne(cotisations, "072")["S21.G00.81.004"] == "217.03"
    assert _ligne(cotisations, "072")["S21.G00.81.003"] == "2359.01"


def test_apec_se_declare_sans_identifiant_urssaf():
    """L'Apec est recouvrée par l'Agirc-Arrco : pas d'OPS Urssaf en 81.002."""
    _, cotisations, _ = build_bases_and_cotisations(
        [
            {
                "coti_id": "apec",
                "base": 3855.98,
                "taux_salarial": 0.00024,
                "montant_salarial": 0.93,
                "taux_patronal": 0.00036,
                "montant_patronal": 1.39,
            }
        ],
        brut=3855.98,
        period_start=PERIODE[0],
        period_end=PERIODE[1],
        default_ops="79484650100011",
    )
    apec = _ligne(cotisations, "132")
    assert "S21.G00.81.002" not in apec
    assert apec["S21.G00.81.004"] == "2.32"
    # CT 2026 : assiette et taux « non concernés » pour l'Agirc-Arrco, comme 131.
    assert "S21.G00.81.003" not in apec
    assert apec["S21.G00.81.007"] == "0.000"


def test_reduction_salariale_heures_sup_au_taux_legal_arrondi():
    """Le bulletin porte le taux effectif (-11,3093 %) ; la DSN déclare 11,310."""
    _, cotisations, _ = _construire(
        [
            {
                "coti_id": "reduction_hs_salariale",
                "base": 449.54,
                "taux_salarial": -0.113093,
                "montant_salarial": -50.84,
            }
        ]
    )
    assert _ligne(cotisations, "114")["S21.G00.81.007"] == "11.310"


def test_la_prevoyance_generique_va_sur_une_base_31():
    """« prevoyance » sans précision tombait sur la base 03 par son libellé :
    un 059 hors base 31 est refusé (CCH-13), et son assiette de tranche A
    (4 005 €) gonflait la base 03 d'un cadre payé 3 750 €."""
    bases, cotisations, _ = _construire(
        [
            {
                "coti_id": "prevoyance",
                "libelle": "GAN PREVOYANCE CADRE TA",
                "base": 4005.0,
                "montant_salarial": 14.62,
                "montant_patronal": 73.09,
            }
        ],
        brut=3750.0,
    )
    assert all(c.rubriques["_base"].startswith("31") for c in cotisations if c.code == "059")
    base_03 = next(b for b in bases if b.code == "03")
    assert base_03.rubriques["S21.G00.78.004"] == "3750.00"


def test_la_base_03_est_toujours_le_brut():
    """Assiette brute déplafonnée : le brut, quelle que soit l'assiette d'une ligne."""
    bases, _, _ = _construire(
        [{"coti_id": "csa", "base": 4200.0, "taux_patronal": 0.003, "montant_patronal": 12.6}],
        brut=3750.0,
    )
    base_03 = next(b for b in bases if b.code == "03")
    assert base_03.rubriques["S21.G00.78.004"] == "3750.00"
