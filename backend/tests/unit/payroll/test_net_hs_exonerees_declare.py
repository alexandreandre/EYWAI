"""Ligne « Montant net des heures compl/suppl exo. » du bulletin.

Le modèle de bulletin clarifié impose, sous le bloc impôt, le montant net des
heures supplémentaires exonérées d'impôt. C'est ce montant que le salarié
retrouve sur sa déclaration : il entre dans son revenu fiscal de référence.
Notre bulletin ne l'imprimait pas du tout.

Sa valeur, relevée sur les bulletins du cabinet de Colorplast — 27 bulletins de
janvier à juillet 2026, dont 22 avec des heures supplémentaires — est toujours :

    rémunération brute des HS − 6,8 % de la base CSG des HS

soit la CSG déductible afférente, et elle seule. La formule tombe juste 27 fois
sur 27 ; retrancher les 9,7 % de CSG/CRDS entière ne tombe jamais. C'est
cohérent avec la nature de la ligne : un montant *imposable* ne se diminue pas
d'une CSG non déductible ni de la CRDS, qui par construction ne réduisent pas
le revenu imposable.

Ce montant est distinct de la somme que le moteur retranche du net imposable :
celui-ci converge déjà au centime avec le cabinet, par une décomposition
équivalente mais différente (le cabinet retranche le brut des HS d'une base qui
n'a jamais vu passer la CSG des HS ; nous retranchons un net d'une base qui
l'exclut). On ne touche donc pas à cette arithmétique.

Chiffres repris des bulletins de janvier 2026 (env. de test).
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.modules.payroll.engine import calcul_net

pytestmark = pytest.mark.unit

#: Bugny, janvier : 691,78 € d'heures sup, base CSG 679,67.
BRUT_HS_BUGNY = 691.78
BASE_CSG_HS_BUGNY = 679.67
ATTENDU_BUGNY = 645.56

#: Girerd, janvier : 442,90 / 435,15 → 413,31.
BRUT_HS_GIRERD = 442.91
BASE_CSG_HS_GIRERD = 435.16
ATTENDU_GIRERD = 413.32


def _contexte():
    return SimpleNamespace(
        month=1,
        cumuls={},
        contrat={"specificites_paie": {}},
        get_cotisation_by_id=lambda _id: {"salarial": 0.068},
    )


def _lignes(base_csg_hs, taux=0.097):
    return [
        {"libelle": "CSG déductible", "base": 2334.11, "montant_salarial": 158.72},
        {
            "libelle": "CSG/CRDS non déductible",
            "base": 2334.11,
            "montant_salarial": 67.69,
        },
        {
            "libelle": "CSG/CRDS sur HS non déductible",
            "base": base_csg_hs,
            "taux_salarial": taux,
            "montant_salarial": round(base_csg_hs * taux, 2),
        },
    ]


class TestMontantNetHeuresSupExonerees:
    def test_bugny(self):
        montant = calcul_net.montant_net_hs_exonerees(
            _contexte(), _lignes(BASE_CSG_HS_BUGNY), BRUT_HS_BUGNY
        )
        assert montant == pytest.approx(ATTENDU_BUGNY, abs=0.01)

    def test_girerd(self):
        montant = calcul_net.montant_net_hs_exonerees(
            _contexte(), _lignes(BASE_CSG_HS_GIRERD), BRUT_HS_GIRERD
        )
        assert montant == pytest.approx(ATTENDU_GIRERD, abs=0.01)

    def test_sans_heures_sup_le_montant_est_nul(self):
        assert calcul_net.montant_net_hs_exonerees(_contexte(), _lignes(0.0), 0.0) == 0.0

    def test_sans_ligne_csg_sur_hs_on_retranche_la_csg_du_brut_hs(self):
        """Heures sup saisies à la main, sans ligne de CSG dédiée : on applique
        le taux à la rémunération des HS abattue, plutôt que de rendre le brut."""
        lignes = [l for l in _lignes(0.0) if "sur HS" not in l["libelle"]]
        montant = calcul_net.montant_net_hs_exonerees(
            _contexte(), lignes, BRUT_HS_BUGNY
        )
        assert montant < BRUT_HS_BUGNY
        assert montant == pytest.approx(BRUT_HS_BUGNY * (1 - 0.068 * 0.9825), abs=0.5)

    def test_le_taux_vient_du_bareme_pas_du_code(self):
        contexte = _contexte()
        contexte.get_cotisation_by_id = lambda _id: {"salarial": 0.05}
        montant = calcul_net.montant_net_hs_exonerees(
            contexte, _lignes(BASE_CSG_HS_BUGNY), BRUT_HS_BUGNY
        )
        assert montant == pytest.approx(BRUT_HS_BUGNY - 0.05 * BASE_CSG_HS_BUGNY, abs=0.01)
