"""Le montant net social comprend les parts patronales santé et prévoyance.

BOSS, « Montant net social » (version au 01/11/2026), II.A.1 : sont pris en
compte « la part patronale pour le financement des garanties collectives à la
complémentaire santé obligatoire […] ainsi que pour le financement des
garanties collectives mentionnées à l'article L. 911-1 » ; II.C.29 : « La
contribution patronale à la complémentaire santé […] doit être intégrée au
montant net social » et de même pour la prévoyance. Arrêté du 25/02/2016
modifié, art. 1er, II, 1° : « la totalité […] du financement prévu au III de
l'article L. 911-7 ».

Audit du 01/11/2026 (thème 7) : l'ancien logiciel ne les ajoutait jamais, dans
les 7 sociétés ; Martine l'imitait (« MNS = net à payer avant impôt »).
"""

from types import SimpleNamespace

import pytest

from app.modules.payroll.engine import calcul_net
from app.modules.payroll.engine.protection_sociale import parts_patronales_protection_sociale

pytestmark = pytest.mark.unit

BRUT = 3124.90
COTISATIONS = 680.00
MUTUELLE = {"coti_id": "mutuelle", "libelle": "Mutuelle", "montant_salarial": 29.24, "montant_patronal": 29.23}
PREVOYANCE = {"coti_id": "prevoyance_non_cadre", "libelle": "Prévoyance", "montant_salarial": 14.53, "montant_patronal": 14.53}
VIEILLESSE = {"coti_id": "vieillesse_plafonnee", "libelle": "Vieillesse", "montant_salarial": 215.62, "montant_patronal": 267.18}

SANS_MUTUELLE = SimpleNamespace(month=3, cumuls={}, contrat={"specificites_paie": {"mutuelle": {"adhesion": False}}})


def test_les_parts_patronales_entrent_dans_le_net_social():
    mns = calcul_net.calculer_montant_net_social(
        SANS_MUTUELLE, BRUT, COTISATIONS, [], lignes_cotisations=[MUTUELLE, PREVOYANCE, VIEILLESSE]
    )
    assert mns == round(BRUT - COTISATIONS + 29.23 + 14.53, 2)


def test_sans_lignes_le_net_social_ne_change_pas():
    assert calcul_net.calculer_montant_net_social(SANS_MUTUELLE, BRUT, COTISATIONS, []) == round(BRUT - COTISATIONS, 2)


def test_les_autres_parts_patronales_n_y_entrent_pas():
    assert parts_patronales_protection_sociale([VIEILLESSE]) == (0.0, 0.0)


def test_le_libelle_suffit_sans_identifiant():
    lignes = [{"libelle": "GAN Mutuelle isolé", "montant_patronal": 29.23},
              {"libelle": "GAN Prévoyance non cadre TA", "montant_patronal": 14.53}]
    assert parts_patronales_protection_sociale(lignes) == (29.23, 14.53)


def test_le_bulletin_calcule_porte_les_parts_patronales():
    from tests.unit.payroll.helpers import build_test_contexte

    contexte = build_test_contexte()
    nets = calcul_net.calculer_net_et_impot(contexte, BRUT, [MUTUELLE, PREVOYANCE, VIEILLESSE], COTISATIONS, [], 0.0)
    sans = calcul_net.calculer_net_et_impot(contexte, BRUT, [VIEILLESSE], COTISATIONS, [], 0.0)
    assert round(nets["montant_net_social"] - sans["montant_net_social"], 2) == round(29.23 + 14.53, 2)


def test_une_retenue_saisie_en_prime_non_soumise_ne_baisse_pas_le_net_social():
    """Une « prime non soumise » négative est une retenue (prêt, acompte). Le
    montant net social compte les revenus « même en cas de saisies sur salaire »
    (BOSS, Montant net social, II.A.1) : une retenue ne le réduit pas. C'est le
    défaut de l'ancien logiciel chez Mont Blanc (prêt retiré du MNS), que Martine
    ne doit pas reproduire. (Le net à payer, lui, garde la retenue.)"""
    base = calcul_net.calculer_montant_net_social(SANS_MUTUELLE, BRUT, COTISATIONS, [])
    avec_retenue = calcul_net.calculer_montant_net_social(
        SANS_MUTUELLE, BRUT, COTISATIONS, [{"libelle": "Remboursement de prêt", "montant": -400.0}]
    )
    assert avec_retenue == base


def test_une_prime_non_soumise_positive_entre_toujours_dans_le_net_social():
    avec_prime = calcul_net.calculer_montant_net_social(
        SANS_MUTUELLE, BRUT, COTISATIONS, [{"libelle": "Prime non soumise", "montant": 50.0}]
    )
    assert avec_prime == round(BRUT - COTISATIONS + 50.0, 2)
