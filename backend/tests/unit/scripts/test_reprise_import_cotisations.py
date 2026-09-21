"""Les cotisations d'un bulletin repris s'assoient sur le brut du PDF.

Constat du 21/09/2026 : les lignes de brut venaient du PDF mais les
cotisations restaient celles du rejeu, assises sur un brut différent (Bugny
juin : base 3 048,73 au lieu de 3 084,43, et neuf euros d'écart sur le total
patronal, lu par la provision comptable des congés).
"""

from __future__ import annotations

import pytest

from scripts.reprise_colorplast_import_litteral import (
    _asseoir_la_structure,
    _asseoir_les_cotisations,
    _synthese_du_pdf,
)

pytestmark = pytest.mark.unit

ANCIEN_BRUT = 3048.73
NOUVEAU_BRUT = 3084.43


def _cotisations() -> list[dict]:
    return [
        {
            "code": "sante",
            "libelle": "Santé",
            "total_salarial": 0.0,
            "total_patronal": 396.33,
            "lignes": [
                {
                    "coti_id": "securite_sociale_maladie",
                    "libelle": "Sécurité sociale - Maladie",
                    "base": ANCIEN_BRUT,
                    "taux_patronal": 0.13,
                    "taux_salarial": None,
                    "montant_patronal": 396.33,
                    "montant_salarial": 0.0,
                }
            ],
        },
        {
            "code": "retraite",
            "libelle": "Retraite",
            "total_salarial": 122.25,
            "total_patronal": 183.23,
            "lignes": [
                {
                    "coti_id": "retraite_comp_t1",
                    "libelle": "Retraite Complémentaire Tranche 1",
                    "base": ANCIEN_BRUT,
                    "taux_patronal": 0.0472,
                    "taux_salarial": 0.0315,
                    "montant_patronal": 143.90,
                    "montant_salarial": 96.03,
                },
                {
                    "coti_id": "ceg_t1",
                    "libelle": "CEG T1",
                    "base": ANCIEN_BRUT,
                    "taux_patronal": 0.0129,
                    "taux_salarial": 0.0086,
                    "montant_patronal": 39.33,
                    "montant_salarial": 26.22,
                },
            ],
        },
        {
            "code": "autres",
            "libelle": "Autres",
            "total_salarial": 0.0,
            "total_patronal": 29.24,
            "lignes": [
                {
                    "coti_id": "mutuelle",
                    "libelle": "Mutuelle (forfait)",
                    "base": 29.24,
                    "taux_patronal": None,
                    "taux_salarial": None,
                    "montant_patronal": 29.24,
                    "montant_salarial": 0.0,
                }
            ],
        },
    ]


class TestAsseoirLesCotisations:
    def test_la_base_devient_le_brut_du_pdf(self):
        sortie = _asseoir_les_cotisations(_cotisations(), NOUVEAU_BRUT)
        bases = [l["base"] for g in sortie for l in g["lignes"] if l["coti_id"] != "mutuelle"]
        assert bases == [NOUVEAU_BRUT, NOUVEAU_BRUT, NOUVEAU_BRUT]

    def test_les_montants_sont_recalcules_avec_nos_taux(self):
        sortie = _asseoir_les_cotisations(_cotisations(), NOUVEAU_BRUT)
        maladie = sortie[0]["lignes"][0]
        assert maladie["montant_patronal"] == pytest.approx(400.98, abs=0.01)  # Quadra

    def test_un_regroupement_quadra_retrouve_son_total(self):
        """« Complémentaire Tranche 1 » chez Quadra = nos deux lignes T1 + CEG."""
        sortie = _asseoir_les_cotisations(_cotisations(), NOUVEAU_BRUT)
        retraite = sortie[1]
        assert retraite["total_patronal"] == pytest.approx(185.38, abs=0.02)  # Quadra
        assert retraite["total_salarial"] == pytest.approx(123.69, abs=0.02)  # Quadra

    def test_une_cotisation_forfaitaire_ne_bouge_pas(self):
        sortie = _asseoir_les_cotisations(_cotisations(), NOUVEAU_BRUT)
        mutuelle = sortie[2]["lignes"][0]
        assert mutuelle["base"] == 29.24 and mutuelle["montant_patronal"] == 29.24

    def test_sans_changement_de_brut_rien_ne_bouge(self):
        avant = _cotisations()
        assert _asseoir_les_cotisations(avant, ANCIEN_BRUT) == avant

    def test_un_brut_nul_laisse_tout_en_place(self):
        avant = _cotisations()
        assert _asseoir_les_cotisations(avant, 0.0) == avant

    def test_rejouer_l_import_rassoit_encore_les_cotisations(self):
        """Le brut du bulletin est déjà celui du PDF au second passage : c'est
        la base des cotisations qui dit sur quoi elles étaient assises."""
        une_fois = _asseoir_les_cotisations(_cotisations(), NOUVEAU_BRUT)
        deux_fois = _asseoir_les_cotisations(une_fois, NOUVEAU_BRUT)
        assert deux_fois == une_fois


class TestStructureDAffichage:
    """`structure_cotisations` (les blocs imprimés) s'assoit aussi sur le brut du PDF."""

    def _structure(self) -> dict:
        return {
            "total_patronal": 396.33,
            "total_salarial": 96.03,
            "bloc_principales": [
                {
                    "coti_id": "securite_sociale_maladie",
                    "base": ANCIEN_BRUT,
                    "taux_patronal": 0.13,
                    "taux_salarial": None,
                    "montant_patronal": 396.33,
                    "montant_salarial": 0.0,
                },
                {
                    "coti_id": "retraite_comp_t1",
                    "base": ANCIEN_BRUT,
                    "taux_patronal": None,
                    "taux_salarial": 0.0315,
                    "montant_patronal": 0.0,
                    "montant_salarial": 96.03,
                },
            ],
            "bloc_allegements": [
                {
                    "coti_id": "reduction_hs_salariale",
                    "base": 673.48,
                    "taux_salarial": -0.1131,
                    "montant_salarial": -76.17,
                    "montant_patronal": 0.0,
                }
            ],
            "bloc_autres_contributions": {
                "total": 16.77,
                "lignes": [
                    {
                        "coti_id": "CFP",
                        "base": ANCIEN_BRUT,
                        "taux_patronal": 0.0055,
                        "taux_salarial": None,
                        "montant_patronal": 16.77,
                        "montant_salarial": 0.0,
                    }
                ],
            },
        }

    def test_les_lignes_des_blocs_sont_rassises(self):
        sortie = _asseoir_la_structure(self._structure(), NOUVEAU_BRUT)
        maladie = sortie["bloc_principales"][0]
        assert maladie["base"] == NOUVEAU_BRUT
        assert maladie["montant_patronal"] == pytest.approx(400.98, abs=0.01)

    def test_une_base_qui_n_est_pas_le_brut_ne_bouge_pas(self):
        sortie = _asseoir_la_structure(self._structure(), NOUVEAU_BRUT)
        assert sortie["bloc_allegements"][0]["base"] == 673.48

    def test_les_totaux_suivent(self):
        sortie = _asseoir_la_structure(self._structure(), NOUVEAU_BRUT)
        assert sortie["bloc_autres_contributions"]["total"] == pytest.approx(16.96, abs=0.01)
        # 396,33 → 400,98 et 16,77 → 16,96 : le total gagne les deux écarts.
        assert sortie["total_patronal"] == pytest.approx(396.33 + 4.65 + 0.19, abs=0.02)

    def test_une_ligne_dont_le_montant_ne_suit_pas_son_taux_n_est_pas_touchee(self):
        """Réduction générale : le montant sort d'une formule, pas d'un produit."""
        structure = self._structure()
        structure["bloc_allegements"].append(
            {
                "coti_id": "reduction_generale",
                "base": ANCIEN_BRUT,
                "taux_patronal": 0.1896,
                "taux_salarial": None,
                "montant_patronal": 549.06,  # et non 3 048,73 × 0,1896 = 578,04
                "montant_salarial": 0.0,
            }
        )
        sortie = _asseoir_la_structure(structure, NOUVEAU_BRUT)
        reduction = sortie["bloc_allegements"][-1]
        assert reduction["base"] == ANCIEN_BRUT and reduction["montant_patronal"] == 549.06

    def test_rejouer_ne_change_plus_rien(self):
        une = _asseoir_la_structure(self._structure(), NOUVEAU_BRUT)
        assert _asseoir_la_structure(une, NOUVEAU_BRUT) == une


class TestSyntheseDuPdf:
    """Les nets imprimés par Quadra sont copiés, pas recalculés."""

    def test_les_nets_viennent_du_pdf(self):
        from scripts.backtest.colorplast_lignes_quadra import Bulletin

        b = Bulletin(matricule="BUGNY", pages=[1])
        b.net = {
            "net_imposable": 1930.60, "mns": 2889.30, "net_a_payer": 2823.66,
            "net_hs_exo": 661.80, "pas_base": 1930.60, "pas_taux": 3.4, "pas_montant": 65.64,
        }
        synthese = _synthese_du_pdf({"synthese_net": {"acompte_verse": 12.0}}, b)
        assert synthese["net_imposable"] == 1930.60
        assert synthese["montant_net_social"] == 2889.30
        assert synthese["net_social_avant_impot"] == 2889.30
        assert synthese["montant_net_hs_exonerees"] == 661.80
        assert synthese["impot_prelevement_a_la_source"] == {
            "base": 1930.60, "taux": 3.4, "montant": 65.64
        }
        assert synthese["acompte_verse"] == 12.0  # ce que le PDF ne dit pas est conservé

    def test_sans_nets_dans_le_pdf_rien_n_est_ecrase(self):
        from scripts.backtest.colorplast_lignes_quadra import Bulletin

        avant = {"synthese_net": {"net_imposable": 1.0}}
        assert _synthese_du_pdf(avant, Bulletin(matricule="X", pages=[1])) == {"net_imposable": 1.0}
