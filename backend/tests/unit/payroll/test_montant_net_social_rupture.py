"""Montant net social d'un bulletin de sortie : la part exonérée d'une indemnité
de rupture en fait partie.

BOSS, « Montant net social » (version en vigueur au 01/10/2026, mise à jour le
02/10/2026, ouverte le 11/10/2026) :
- II, A, 1 : « L'ensemble de la rémunération brute du salarié est pris en
  compte, indépendamment des exonérations, déductions, abattements ou
  franchises applicables et de l'assujettissement fiscal ou social. » ; au
  tableau des « Eléments pris en compte dans le MNS » : « Les indemnités de
  rupture de toute nature » ;
- II, B, question 20 : « Les indemnités de rupture conventionnelle doivent bien
  être intégrées dans le montant net social. » ;
- II, A, 2 : en sont déduites les cotisations et contributions sociales
  obligatoires à la charge du salarié, CSG et CRDS comprises.

Martine ajoutait la part exonérée de cotisations au net à payer, pas au montant
net social : le bulletin de sortie d'une rupture conventionnelle de 15 000 €
affichait (et la DSN aurait déclaré) un montant net social amputé de 15 000 €.
La CSG/CRDS de la part au-delà du minimum est déjà dans les cotisations
salariales, donc déjà déduite.
"""

from __future__ import annotations

import pytest

from app.modules.payroll.engine.bulletin import creer_bulletin_sortie
from app.modules.payroll.engine.regime_indemnites_rupture import ventiler_indemnite_de_rupture
from tests.unit.payroll.helpers import build_test_contexte

pytestmark = pytest.mark.unit

_NETS = {
    "net_a_payer": 1900.0,
    "net_imposable": 1950.0,
    "montant_net_social": 1880.0,
    "montant_impot_pas": 0.0,
}


def _bulletin(dossier: dict) -> dict:
    contexte = build_test_contexte(salaire_base=2400.0)
    contexte.exit_indemnities = dossier
    return creer_bulletin_sortie(contexte, 2400.0, [], [], dict(_NETS), [], dossier, 2026, 10)


def test_la_part_exoneree_d_une_rupture_conventionnelle_entre_au_montant_net_social():
    regime = ventiler_indemnite_de_rupture(
        "rupture_conventionnelle", 15000.0, minimum=4000.0, remuneration_annuelle_n_1=30000.0,
        pass_annuel=48060.0,
    ).en_dict()
    bulletin = _bulletin(
        {
            "indemnite_rupture_conventionnelle": {
                "montant": 15000.0,
                "montant_negocie": 15000.0,
                "montant_minimum": 4000.0,
                "regime_social": regime,
            }
        }
    )

    synthese = bulletin["synthese_net"]
    assert synthese["montant_net_social"] == round(1880.0 + 15000.0, 2)
    assert synthese["net_social_avant_impot"] == round(1900.0 + 15000.0, 2)
    assert bulletin["net_a_payer"] == round(1900.0 + 15000.0, 2)


def test_une_indemnite_legale_de_licenciement_entre_au_montant_net_social():
    regime = ventiler_indemnite_de_rupture(
        "licenciement", 3200.0, minimum=3200.0, remuneration_annuelle_n_1=30000.0, pass_annuel=48060.0
    ).en_dict()
    bulletin = _bulletin({"indemnite_licenciement": {"montant": 3200.0, "regime_social": regime}})

    assert bulletin["synthese_net"]["montant_net_social"] == round(1880.0 + 3200.0, 2)


def test_sans_indemnite_de_rupture_le_montant_net_social_ne_change_pas():
    bulletin = _bulletin({"indemnite_preavis": {"montant": 0.0}, "indemnite_conges": {"montant": 0.0}})

    assert bulletin["synthese_net"]["montant_net_social"] == 1880.0
