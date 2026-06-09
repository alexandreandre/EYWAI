"""Tests unitaires — calcul des augmentations (périmètre brut / brut+HS)."""

import pytest

from app.modules.employees.domain.salary_augmentation import (
    calculer_nouveau_salaire_brut,
    decomposer_salaire_contractuel,
)

pytestmark = pytest.mark.unit


class TestDecomposerSalaireContractuel:
    def test_temps_plein_35h_sans_hs(self):
        deco = decomposer_salaire_contractuel(2000.0, 35.0)
        assert deco["base_35h"] == 2000.0
        assert deco["part_hs"] == 0.0
        assert deco["a_hs_structurelles"] is False

    def test_39h_a_hs_structurelles(self):
        deco = decomposer_salaire_contractuel(2600.0, 39.0, majoration_hs=0.25)
        assert deco["a_hs_structurelles"] is True
        assert deco["base_35h"] > 0
        assert deco["part_hs"] > 0
        assert deco["base_35h"] + deco["part_hs"] == pytest.approx(2600.0, abs=0.02)


class TestCalculerNouveauSalaireBrut:
    def test_pourcentage_sur_brut_et_hs(self):
        res = calculer_nouveau_salaire_brut(
            2600.0, 39.0, "pourcentage", 3.0, "brut_et_hs", majoration_hs=0.25
        )
        assert res["nouveau_salaire_brut"] == pytest.approx(2678.0, abs=0.02)
        assert res["difference_brut"] == pytest.approx(78.0, abs=0.02)
        assert res["taux_augmentation_reel"] == pytest.approx(3.0, abs=0.1)

    def test_pourcentage_sur_brut_seul_39h(self):
        res = calculer_nouveau_salaire_brut(
            2600.0, 39.0, "pourcentage", 3.0, "brut_seul", majoration_hs=0.25
        )
        assert res["nouveau_salaire_brut"] < 2678.0
        assert res["nouveau_part_hs"] == pytest.approx(res["ancien_part_hs"], abs=0.02)
        assert res["nouveau_base_35h"] > res["ancien_base_35h"]

    def test_montant_fixe_sur_brut_seul(self):
        res = calculer_nouveau_salaire_brut(
            2600.0, 39.0, "montant_fixe", 100.0, "brut_seul", majoration_hs=0.25
        )
        assert res["nouveau_salaire_brut"] == pytest.approx(2700.0, abs=0.02)
        assert res["nouveau_part_hs"] == pytest.approx(res["ancien_part_hs"], abs=0.02)

    def test_35h_brut_seul_equivaut_brut_et_hs(self):
        res_seul = calculer_nouveau_salaire_brut(
            2000.0, 35.0, "pourcentage", 5.0, "brut_seul"
        )
        res_total = calculer_nouveau_salaire_brut(
            2000.0, 35.0, "pourcentage", 5.0, "brut_et_hs"
        )
        assert res_seul["nouveau_salaire_brut"] == res_total["nouveau_salaire_brut"]

    def test_montant_fixe_sur_total(self):
        res = calculer_nouveau_salaire_brut(2000.0, 35.0, "montant_fixe", 150.0, "brut_et_hs")
        assert res["nouveau_salaire_brut"] == 2150.0
        assert res["difference_brut"] == 150.0
