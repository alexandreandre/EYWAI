"""Les cotisations qui ne suivent pas le brut sont copiées du PDF, une à une.

CSG (base composite), réduction générale (formule), allègements sur heures
sup (base = heures) : rasseoir sur le brut ne suffit pas, il faut prendre le
montant imprimé par Quadra. Le signe reste le nôtre.
"""

from __future__ import annotations

import pytest

from scripts.backtest.colorplast_lignes_quadra import Bulletin, Ligne
from scripts.reprise_colorplast_import_litteral import (
    _copier_les_cotisations_du_pdf,
    _lignes_de_cotisation_du_pdf,
)

pytestmark = pytest.mark.unit


def _bulletin() -> Bulletin:
    b = Bulletin(matricule="BUGNY", pages=[1])
    b.lignes = [
        Ligne(None, "SALAIRE BRUT", gain=3084.43),
        Ligne(None, "CSG déductible à l'IR", base=2404.85, taux=6.8, montant_sal=163.53, section="Q800"),
        Ligne(None, "EXO., ECRET. ET ALLEG. COTIS", base=552.97, montant_pat=552.97, section="Q802"),
        Ligne("EWA2", "REDUCTION SALARIALE HS/HC 2019", base=709.18, taux=-11.31, montant_sal=-80.21, section="Q802"),
        Ligne("EWZB", "REDUCT HEURES SUPPL. P.P.<= 20", base=38.33, montant_pat=-57.5, section="Q802"),
        Ligne(None, "CSG/CRDS non déductible à l'IR", base=2404.85, taux=2.9, montant_sal=69.74),
        Ligne(None, "CSG/CRDS non déductible à l'IR", base=696.7, taux=9.7, montant_sal=67.58),
    ]
    return b


def _structure() -> dict:
    return {
        "total_patronal": 783.73,
        "total_salarial": 611.03,
        "bloc_principales": [
            {"coti_id": "csg_deductible", "base": 2377.09, "taux_salarial": 0.068,
             "montant_salarial": 161.64, "montant_patronal": 0.0},
        ],
        "bloc_allegements": [
            {"coti_id": "reduction_hs_salariale", "base": 673.48, "taux_salarial": -0.1131,
             "montant_salarial": -76.17, "montant_patronal": 0.0},
            {"coti_id": "deduction_hs_patronale", "base": 36.33, "montant_salarial": 0.0,
             "montant_patronal": -54.5},
            {"coti_id": "reduction_generale", "base": 3048.73, "taux_patronal": 0.1896,
             "montant_salarial": 0.0, "montant_patronal": -549.06},
        ],
        "bloc_csg_non_deductible": [
            {"coti_id": "csg_non_deductible", "base": 2377.09, "taux_salarial": 0.029,
             "montant_salarial": 68.94, "montant_patronal": 0.0},
            {"coti_id": "csg_non_deductible", "base": 661.69, "taux_salarial": 0.097,
             "montant_salarial": 64.18, "montant_patronal": 0.0},
        ],
    }


class TestLecture:
    def test_les_cotisations_du_pdf_sont_rangees_par_identifiant(self):
        lues = _lignes_de_cotisation_du_pdf(_bulletin())
        assert [round(x, 2) for x in lues["csg_non_deductible"]["montants"]] == [69.74, 67.58]
        assert lues["reduction_generale"]["montants"] == [552.97]

    def test_le_salaire_brut_et_les_lignes_de_gain_sont_ignores(self):
        assert "salaire_brut" not in _lignes_de_cotisation_du_pdf(_bulletin())


class TestCopie:
    def test_la_reduction_generale_vient_du_pdf_et_garde_notre_signe(self):
        sortie = _copier_les_cotisations_du_pdf(_structure(), _bulletin())
        reduction = sortie["bloc_allegements"][2]
        assert reduction["montant_patronal"] == pytest.approx(-552.97)

    def test_les_deux_lignes_de_csg_non_deductible_suivent_l_ordre(self):
        sortie = _copier_les_cotisations_du_pdf(_structure(), _bulletin())
        montants = [x["montant_salarial"] for x in sortie["bloc_csg_non_deductible"]]
        assert montants == pytest.approx([69.74, 67.58])
        bases = [x["base"] for x in sortie["bloc_csg_non_deductible"]]
        assert bases == pytest.approx([2404.85, 696.70])

    def test_les_allegements_sur_heures_sup_gardent_leur_signe(self):
        sortie = _copier_les_cotisations_du_pdf(_structure(), _bulletin())
        assert sortie["bloc_allegements"][0]["montant_salarial"] == pytest.approx(-80.21)
        assert sortie["bloc_allegements"][1]["montant_patronal"] == pytest.approx(-57.5)

    def test_les_totaux_suivent_les_ecarts(self):
        sortie = _copier_les_cotisations_du_pdf(_structure(), _bulletin())
        # patronal : réduction générale −549,06 → −552,97 et déduction −54,50 → −57,50
        assert sortie["total_patronal"] == pytest.approx(783.73 - 3.91 - 3.0, abs=0.02)

    def test_rejouer_ne_change_plus_rien(self):
        une = _copier_les_cotisations_du_pdf(_structure(), _bulletin())
        assert _copier_les_cotisations_du_pdf(une, _bulletin()) == une

    def test_sans_ligne_correspondante_rien_ne_bouge(self):
        vide = Bulletin(matricule="X", pages=[1])
        vide.lignes = []
        assert _copier_les_cotisations_du_pdf(_structure(), vide) == _structure()


class TestPiedDePage:
    """L'allègement du mois et le total versé employeur sont imprimés par
    Quadra dans la colonne de droite : on les copie plutôt que de les sommer."""

    def test_les_deux_totaux_viennent_du_pdf(self):
        from scripts.reprise_colorplast_import_litteral import _pied_de_page_du_pdf

        b = _bulletin()
        b.droite = {"allegement_mois": -610.47, "verse_employeur": 4292.39}
        pied = _pied_de_page_du_pdf({"cout_total_employeur": 4247.73}, b)
        assert pied["total_allegements_patronaux"] == pytest.approx(610.47)
        assert pied["cout_total_employeur"] == pytest.approx(4292.39)

    def test_sans_colonne_de_droite_rien_n_est_ecrase(self):
        from scripts.reprise_colorplast_import_litteral import _pied_de_page_du_pdf

        b = _bulletin()
        b.droite = {}
        assert _pied_de_page_du_pdf({"cout_total_employeur": 1.0}, b) == {
            "cout_total_employeur": 1.0
        }
