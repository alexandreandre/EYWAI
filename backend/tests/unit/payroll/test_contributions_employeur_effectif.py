"""Contributions patronales manquantes, relevées sur Colorplast en janvier 2026.

Le cabinet regroupe ses contributions patronales sous « Autres contrib. dues par
empl. », avec une ligne par assiette. Sur les 43 bulletins de janvier à juillet
2026, la décomposition est constante :

* **1,646 % du brut** pour les sept salariés en CDI — soit formation
  professionnelle 0,55 %, CSA 0,30 %, taxe d'apprentissage 0,59 % + 0,09 % de
  solde, FNAL 0,10 % et dialogue social 0,016 % ;
* **2,646 %** pour Demory et Fuckar, les deux seuls CDD : un point de plus, la
  contribution au financement du compte personnel de formation des titulaires
  de CDD (art. L6331-6 du code du travail) ;
* **8 %** sur la somme des parts patronales de prévoyance et de mutuelle ;
* **20 %** sur la part patronale de retraite supplémentaire, pour le seul cadre
  (Girerd : 19,00 € sur 94,98 €).

EYWAI ne produisait aucune de ces trois dernières lignes pour Colorplast. Le
forfait social existait déjà, mais seulement quand une ligne de prévoyance de la
fiche portait un taux : c'est le cas des deux salariés importés de la DSN, pas
des sept autres, qui passent par le barème global. La retraite supplémentaire
n'avait aucun point d'accroche, et le CPF-CDD n'existait pas.

Chiffres repris des bulletins de janvier 2026 (env. de test).
"""

from __future__ import annotations

import copy

import pytest

from app.modules.payroll.engine.calcul_cotisations import calculer_cotisations

from .fixtures.baremes_snapshot import baremes_snapshot
from .helpers import build_test_contexte

pytestmark = pytest.mark.unit

BRUT_BUGNY = 3023.40
BRUT_GIRERD = 3799.07
BRUT_FUCKAR = 1818.80

CPF_CDD = {
    "id": "cpf_cdd",
    "libelle": "Contribution CPF des titulaires de CDD",
    "base": "brut",
    "salarial": None,
    "patronal": 0.01,
}
#: Prévoyance non-cadre du barème global, avec le taux de forfait social porté
#: par le barème et non par la fiche.
PREVOYANCE_GLOBALE = {
    "id": "prevoyance_non_cadre",
    "libelle": "Prévoyance Non-Cadre Tranche 1",
    "base": "brut_plafonne",
    "salarial": 0.00465,
    "patronal": 0.00465,
    "forfait_social": 0.08,
}
MUTUELLE_ISOLE = {
    "libelle": "Mutuelle Isolé",
    "montant_salarial": 29.24,
    "montant_patronal": 29.23,
}


def _baremes(*cotisations_extra):
    b = copy.deepcopy(baremes_snapshot())
    b["cotisations"]["cotisations"].extend(cotisations_extra)
    return b


def _lignes(contexte, brut):
    lignes, _ = calculer_cotisations(contexte, brut, 0.0, 0.0)
    return lignes


def _ligne(lignes, motif):
    trouvees = [l for l in lignes if motif.lower() in str(l.get("libelle", "")).lower()]
    return trouvees[0] if trouvees else None


class TestContributionCpfCdd:
    def test_un_cdd_paie_un_point_de_plus(self):
        ctx = build_test_contexte(
            salaire_base=BRUT_FUCKAR, duree_hebdo=39.0, effectif=9,
            type_contrat="CDD", baremes=_baremes(CPF_CDD),
        )
        ligne = _ligne(_lignes(ctx, BRUT_FUCKAR), "CPF des titulaires de CDD")
        assert ligne is not None
        assert ligne["montant_patronal"] == pytest.approx(18.19, abs=0.01)

    def test_un_cdi_ne_la_paie_pas(self):
        ctx = build_test_contexte(
            salaire_base=BRUT_BUGNY, duree_hebdo=39.0, effectif=9,
            type_contrat="CDI", baremes=_baremes(CPF_CDD),
        )
        assert _ligne(_lignes(ctx, BRUT_BUGNY), "CPF des titulaires de CDD") is None


class TestForfaitSocialBaremeGlobal:
    """Sept salariés sur neuf n'ont pas de ligne de prévoyance sur leur fiche :
    ils passent par le barème global, qui n'avait pas d'accroche."""

    def test_huit_pourcent_sur_prevoyance_et_mutuelle(self):
        ctx = build_test_contexte(
            salaire_base=BRUT_BUGNY, duree_hebdo=39.0, effectif=9,
            baremes=_baremes(PREVOYANCE_GLOBALE),
            specificites_extra={
                "prevoyance": {"adhesion": True, "lignes_specifiques": []},
                "mutuelle": {"adhesion": True, "lignes_specifiques": [MUTUELLE_ISOLE]},
            },
        )
        lignes = _lignes(ctx, BRUT_BUGNY)
        prevoyance = _ligne(lignes, "Prévoyance Non-Cadre")
        assert prevoyance["montant_patronal"] == pytest.approx(14.06, abs=0.01)
        forfait = _ligne(lignes, "Forfait social")
        assert forfait is not None
        # 14,06 de prévoyance + 29,23 de mutuelle = 43,29 ; 8 % = 3,46.
        assert forfait["base"] == pytest.approx(43.29, abs=0.01)
        assert forfait["montant_patronal"] == pytest.approx(3.46, abs=0.01)

    def test_sans_taux_au_bareme_aucune_ligne(self):
        """Garde anti-régression : sans taux configuré, rien n'apparaît."""
        sans_taux = {k: v for k, v in PREVOYANCE_GLOBALE.items() if k != "forfait_social"}
        ctx = build_test_contexte(
            salaire_base=BRUT_BUGNY, duree_hebdo=39.0, effectif=9,
            baremes=_baremes(sans_taux),
            specificites_extra={
                "prevoyance": {"adhesion": True, "lignes_specifiques": []},
                "mutuelle": {"adhesion": True, "lignes_specifiques": [MUTUELLE_ISOLE]},
            },
        )
        assert _ligne(_lignes(ctx, BRUT_BUGNY), "Forfait social") is None


class TestForfaitSocialRetraiteSupplementaire:
    def test_vingt_pourcent_sur_la_part_patronale(self):
        ctx = build_test_contexte(
            statut="Cadre", salaire_base=BRUT_GIRERD, duree_hebdo=39.0, effectif=9,
            specificites_extra={
                "retraite_sup": {
                    "adhesion": True,
                    "lignes_specifiques": [{
                        "id": "retraite_sup_cadre",
                        "base": "brut_plafonne",
                        "libelle": "Retraite supplémentaire cadre",
                        "patronal": 0.025,
                        "salarial": 0.025,
                        "forfait_social": 0.20,
                    }],
                },
            },
        )
        lignes = _lignes(ctx, BRUT_GIRERD)
        retraite = _ligne(lignes, "Retraite supplémentaire cadre")
        assert retraite["montant_patronal"] == pytest.approx(94.98, abs=0.01)
        forfait = _ligne(lignes, "Forfait social")
        assert forfait is not None
        assert forfait["base"] == pytest.approx(94.98, abs=0.01)
        assert forfait["montant_patronal"] == pytest.approx(19.00, abs=0.01)

    def test_sans_taux_sur_la_ligne_aucun_forfait(self):
        ctx = build_test_contexte(
            statut="Cadre", salaire_base=BRUT_GIRERD, duree_hebdo=39.0, effectif=9,
            specificites_extra={
                "retraite_sup": {
                    "adhesion": True,
                    "lignes_specifiques": [{
                        "id": "retraite_sup_cadre",
                        "base": "brut_plafonne",
                        "libelle": "Retraite supplémentaire cadre",
                        "patronal": 0.025,
                        "salarial": 0.025,
                    }],
                },
            },
        )
        assert _ligne(_lignes(ctx, BRUT_GIRERD), "Forfait social") is None


class TestDeclarationDsn:
    def test_le_cpf_cdd_porte_le_code_129(self):
        """Sans code DSN, une contribution figure au bulletin mais pas à la
        déclaration : le bulletin et la DSN divergeraient."""
        from app.modules.dsn_export.domain.cotisation_mapping import REGLES
        from app.modules.dsn_export.domain.nomenclature_cotisation import (
            CODE_COTISATION_LIBELLE,
        )

        assert REGLES["cpf_cdd"].code == "129"
        assert "CPF-CDD" in CODE_COTISATION_LIBELLE["129"]
