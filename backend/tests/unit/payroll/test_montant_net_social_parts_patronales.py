"""Parts patronales santé et prévoyance dans le montant net social : à partir de 2027.

Version du BOSS « Montant net social » en vigueur du 01/03/2025 au 01/10/2026
(copie archivée du 08/01/2026), question 13 : « L'ensemble des contributions
des employeurs finançant la couverture de garanties collectives en matière de
prévoyance ou de retraite supplémentaire ne doivent pas être prises en compte
dans le montant net social » ; question 28 : la contribution patronale des
garanties collectives « ne doit pas être intégrée au montant net social » ;
question 29 : le versement santé est « à déduire […] au même titre que la part
patronale » de la complémentaire santé.

La mise à jour du BOSS du 02/10/2026 les fait entrer dans le montant net social
pour les revenus dus à compter du 01/01/2027, sous réserve du décret en Conseil
d'État (encore à paraître au 04/11/2026). Le commit 697daa44 (01/11/2026) les
avait ajoutées sans condition de date : faux pour tous les mois de 2026.

Le net à payer, le net imposable et les cotisations ne dépendent pas de cette
date : seul le montant net social bouge.
"""

from datetime import date
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
LIGNES = [MUTUELLE, PREVOYANCE, VIEILLESSE]
PARTS_PATRONALES = round(29.23 + 14.53, 2)

SANS_MUTUELLE = SimpleNamespace(month=3, cumuls={}, contrat={"specificites_paie": {"mutuelle": {"adhesion": False}}})


def _contexte(annee, mois):
    return SimpleNamespace(
        year=annee, month=mois, cumuls={}, contrat={"specificites_paie": {"mutuelle": {"adhesion": False}}}
    )


def _mns(annee, mois, lignes=LIGNES):
    return calcul_net.calculer_montant_net_social(
        _contexte(annee, mois), BRUT, COTISATIONS, [], lignes_cotisations=lignes
    )


def test_la_date_d_entree_est_le_1er_janvier_2027():
    from app.modules.payroll.engine.protection_sociale import DEBUT_PARTS_PATRONALES_DANS_LE_NET_SOCIAL

    assert DEBUT_PARTS_PATRONALES_DANS_LE_NET_SOCIAL == date(2027, 1, 1)


def test_octobre_2026_le_net_social_exclut_les_parts_patronales():
    assert _mns(2026, 10) == round(BRUT - COTISATIONS, 2)


@pytest.mark.parametrize("mois", [1, 6, 9, 12])
def test_aucun_mois_de_2026_ne_les_compte(mois):
    assert _mns(2026, mois) == round(BRUT - COTISATIONS, 2)


def test_janvier_2027_le_net_social_comprend_les_parts_patronales():
    assert _mns(2027, 1) == round(BRUT - COTISATIONS + PARTS_PATRONALES, 2)


def test_periode_inconnue_regle_en_vigueur_sans_les_parts():
    """Sans période, la règle en vigueur aujourd'hui : pas de parts patronales."""
    mns = calcul_net.calculer_montant_net_social(
        SANS_MUTUELLE, BRUT, COTISATIONS, [], lignes_cotisations=LIGNES
    )
    assert mns == round(BRUT - COTISATIONS, 2)


def test_la_fin_de_periode_suffit_sans_annee():
    contexte = SimpleNamespace(
        date_fin_periode=date(2027, 1, 31), cumuls={}, contrat={"specificites_paie": {"mutuelle": {"adhesion": False}}}
    )
    mns = calcul_net.calculer_montant_net_social(contexte, BRUT, COTISATIONS, [], lignes_cotisations=LIGNES)
    assert mns == round(BRUT - COTISATIONS + PARTS_PATRONALES, 2)


def test_sans_lignes_le_net_social_ne_change_pas():
    assert _mns(2027, 1, lignes=[]) == round(BRUT - COTISATIONS, 2)
    assert calcul_net.calculer_montant_net_social(SANS_MUTUELLE, BRUT, COTISATIONS, []) == round(BRUT - COTISATIONS, 2)


def test_les_autres_parts_patronales_n_y_entrent_pas():
    assert parts_patronales_protection_sociale([VIEILLESSE]) == (0.0, 0.0)
    assert _mns(2027, 1, lignes=[VIEILLESSE]) == round(BRUT - COTISATIONS, 2)


def test_le_libelle_suffit_sans_identifiant():
    lignes = [{"libelle": "GAN Mutuelle isolé", "montant_patronal": 29.23},
              {"libelle": "GAN Prévoyance non cadre TA", "montant_patronal": 14.53}]
    assert parts_patronales_protection_sociale(lignes) == (29.23, 14.53)


def _nets_du_bulletin(annee, mois, lignes):
    from tests.unit.payroll.helpers import build_test_contexte

    contexte = build_test_contexte()
    contexte.year = annee
    contexte.month = mois
    return calcul_net.calculer_net_et_impot(contexte, BRUT, lignes, COTISATIONS, [], 0.0)


def test_le_bulletin_d_octobre_2026_ne_porte_pas_les_parts_patronales():
    avec = _nets_du_bulletin(2026, 10, LIGNES)
    sans = _nets_du_bulletin(2026, 10, [VIEILLESSE])
    assert avec["montant_net_social"] == sans["montant_net_social"] == round(BRUT - COTISATIONS, 2)


def test_le_bulletin_de_janvier_2027_porte_les_parts_patronales():
    avec = _nets_du_bulletin(2027, 1, LIGNES)
    sans = _nets_du_bulletin(2027, 1, [VIEILLESSE])
    assert round(avec["montant_net_social"] - sans["montant_net_social"], 2) == PARTS_PATRONALES


def test_seul_le_net_social_depend_de_la_date():
    """Le net à payer et le net imposable du même bulletin ne bougent pas entre
    décembre 2026 et janvier 2027 ; seul le montant net social gagne les parts."""
    decembre = _nets_du_bulletin(2026, 12, LIGNES)
    janvier = _nets_du_bulletin(2027, 1, LIGNES)
    for cle in ("net_a_payer", "net_imposable", "montant_impot_pas", "net_social"):
        assert decembre[cle] == janvier[cle], cle
    assert round(janvier["montant_net_social"] - decembre["montant_net_social"], 2) == PARTS_PATRONALES


def test_une_retenue_saisie_en_prime_non_soumise_ne_baisse_pas_le_net_social():
    """Une « prime non soumise » négative est une retenue (prêt, acompte). Le
    montant net social compte les revenus « même en cas de saisies sur salaire »
    (BOSS, Montant net social, II.A.1) : une retenue ne le réduit pas. C'est le
    défaut de l'ancien logiciel dans une des sociétés (prêt retiré du MNS), que Martine
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
