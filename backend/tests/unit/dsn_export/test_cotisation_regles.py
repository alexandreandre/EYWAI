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
    """La part retraite complémentaire vaut 6,01 / T, T = 39,80 % sous 50 salariés."""
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
    part_retraite = round(-400.0 * 0.0601 / 0.3980, 2)
    assert codes["106"][1] == part_retraite
    assert codes["018"][1] == round(-400.0 - part_retraite, 2)
    assert round(codes["018"][1] + codes["106"][1], 2) == -400.0


def test_le_coefficient_maximal_suit_le_taux_de_fnal():
    """FNAL à 0,50 % ⇒ effectif d'au moins 50 ⇒ T = 40,20 %, donc une autre part."""
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
    assert codes["106"][1] == round(-400.0 * 0.0601 / 0.4020, 2)
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
