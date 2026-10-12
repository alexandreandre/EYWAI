"""Net imposable d'un bulletin de sortie : la part imposable d'une indemnité de
rupture, pas sa part soumise aux cotisations.

Les deux assiettes diffèrent :
- au-delà de 2 PASS, une part soumise aux cotisations peut rester exonérée
  d'impôt (BOSS, « Indemnités de rupture », mis à jour le 26/06/2026, § 50, 60,
  300 et exemple du § 380 : indemnité de 138 000 €, « totalement non
  imposable », cotisations dues sur 41 880 €) ;
- à l'inverse, la rupture conventionnelle d'un salarié qui peut liquider sa
  retraite est imposable dès le premier euro et exonérée de cotisations dans
  les limites (§ 60, 890, 940).
Martine mettait au net imposable la part soumise aux cotisations (et
l'alertait au bulletin, « à corriger à la main »).

CGI, art. 80 duodecies (limites fiscales) ; BOFIP BOI-RSA-BASE-30-30 (version
du 24/07/2017, ouvert le 11/10/2026), § 100 : la CSG des indemnités de rupture
n'est pas déductible pour « leur fraction exonérée d'impôt sur le revenu et de
cotisations de sécurité sociale » ; « En revanche, la CSG due sur la fraction
imposable des indemnités [...] est déductible. Il en est de même de celle due
sur la fraction exonérée d'impôt sur le revenu mais assujettie aux cotisations
de sécurité sociale. » (le taux déductible était alors de 5,1 % ; c'est celui du
barème, 6,8 %, qui s'applique).
"""

from __future__ import annotations

import copy

import pytest

from app.modules.payroll.engine.bulletin import creer_bulletin_sortie
from app.modules.payroll.engine.calcul_net import calculer_net_et_impot
from app.modules.payroll.engine.regime_indemnites_rupture import (
    lignes_cotisations_indemnites_rupture,
    ventiler_indemnite_de_rupture,
)
from tests.unit.payroll.fixtures.baremes_snapshot import baremes_snapshot
from tests.unit.payroll.helpers import build_test_contexte

pytestmark = pytest.mark.unit

PASS_2026 = 48060.0


def _baremes() -> dict:
    baremes = copy.deepcopy(baremes_snapshot())
    cle = next(k for k, v in baremes["cotisations"].items() if isinstance(v, list))
    lignes = [
        c for c in baremes["cotisations"][cle] if c.get("id") not in ("csg_deductible", "csg_non_deductible", "crds")
    ]
    lignes.append(
        {"id": "csg", "libelle": "CSG/CRDS", "base": "brut", "salarial": {"deductible": 0.068, "non_deductible": 0.029}}
    )
    baremes["cotisations"][cle] = lignes
    return baremes


def _contexte(dossier: dict | None):
    contexte = build_test_contexte(salaire_base=2400.0, baremes=_baremes())
    contexte.exit_indemnities = dossier
    return contexte


def _net_imposable(dossier: dict | None) -> float:
    return calculer_net_et_impot(_contexte(dossier), 5000.0, [], 0.0, [], 0.0)["net_imposable"]


def _licenciement_138000() -> dict:
    regime = ventiler_indemnite_de_rupture(
        "licenciement", 138000.0, minimum=120000.0, remuneration_annuelle_n_1=250000.0, pass_annuel=PASS_2026
    ).en_dict()
    return {"indemnite_licenciement": {"montant": 138000.0, "regime_social": regime}}


def _rupture_pension() -> dict:
    regime = ventiler_indemnite_de_rupture(
        "rupture_conventionnelle", 30000.0, minimum=8000.0, remuneration_annuelle_n_1=30000.0,
        pass_annuel=PASS_2026, pension_de_retraite=True,
    ).en_dict()
    return {
        "indemnite_rupture_conventionnelle": {
            "montant": 30000.0, "montant_negocie": 30000.0, "montant_minimum": 8000.0, "regime_social": regime,
        }
    }


def test_au_dela_de_deux_pass_la_part_soumise_non_imposable_sort_du_net_imposable():
    # Le brut porte les 41 880 € soumis aux cotisations ; aucun n'est imposable.
    assert _net_imposable(_licenciement_138000()) == round(_net_imposable(None) - 41880.0, 2)


def test_une_rupture_avec_pension_liquidable_entre_au_net_imposable_des_le_premier_euro():
    assert _net_imposable(_rupture_pension()) == round(_net_imposable(None) + 30000.0, 2)


def test_sans_ecart_entre_les_deux_assiettes_le_net_imposable_ne_bouge_pas():
    regime = ventiler_indemnite_de_rupture(
        "rupture_conventionnelle", 15000.0, minimum=4000.0, remuneration_annuelle_n_1=30000.0,
        pass_annuel=PASS_2026,
    ).en_dict()
    dossier = {"indemnite_rupture_conventionnelle": {"montant": 15000.0, "montant_negocie": 15000.0, "regime_social": regime}}
    assert _net_imposable(dossier) == _net_imposable(None)


def _par_libelle(dossier: dict) -> dict:
    return {l["libelle"]: l for l in lignes_cotisations_indemnites_rupture(_contexte(dossier))}


def test_la_csg_d_une_part_imposable_exoneree_de_cotisations_est_deductible():
    lignes = _par_libelle(_rupture_pension())
    # 30 000 − 8 000 exonérés de CSG : 22 000 imposables, CSG déductible.
    assert lignes["CSG déductible sur indemnité de rupture"]["base"] == 22000.0
    assert lignes["CSG/CRDS non déductible sur indemnité de rupture"]["base"] == 22000.0
    assert "CSG/CRDS non déductible sur indemnité de rupture non imposable" not in lignes


def test_la_csg_d_une_part_soumise_non_imposable_reste_deductible():
    lignes = _par_libelle(_licenciement_138000())
    assert lignes["CSG déductible sur indemnité de rupture"]["base"] == 41880.0
    assert "CSG/CRDS non déductible sur indemnité de rupture non imposable" not in lignes


def test_le_bulletin_ne_demande_plus_de_corriger_le_net_imposable_a_la_main():
    dossier = _licenciement_138000()
    nets = {"net_a_payer": 1900.0, "net_imposable": 1950.0, "montant_net_social": 1880.0}
    bulletin = creer_bulletin_sortie(_contexte(dossier), 2400.0, [], [], nets, [], dossier, 2026, 10)
    codes = [a.get("code") for a in bulletin.get("alertes_baremes") or []]
    assert "indemnite_rupture_net_imposable" not in codes
