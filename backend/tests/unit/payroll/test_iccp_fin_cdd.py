"""Indemnité de CP de fin de CDD : la méthode « salaire rétabli, solde N-1 inclus ».

Recette : Aurélien Demory, Colorplast, juillet 2026 — Quadra 940,23 sur une
assiette de 9 402,30 (spec 2026-09-21-indemnite-cp-fin-cdd-methode-design.md).
"""

from __future__ import annotations

import pytest

from app.modules.payroll.engine.iccp_fin_cdd import (
    METHODE_PAR_DEFAUT,
    METHODE_SALAIRE_RETABLI,
    assiette_salaire_retabli,
    mention,
    methode_depuis_parametres,
    salaire_retabli_du_mois,
    valeur_jour_maintien,
)


class TestMethode:
    def test_par_defaut_la_remuneration_versee(self):
        assert methode_depuis_parametres({}) == METHODE_PAR_DEFAUT == "remuneration_versee"
        assert methode_depuis_parametres({"parametres_paie": {}}) == METHODE_PAR_DEFAUT
        assert methode_depuis_parametres(None) == METHODE_PAR_DEFAUT

    def test_la_methode_choisie_est_lue(self):
        entreprise = {"parametres_paie": {"indemnite_cp_fin_cdd": "salaire_retabli_solde_n1"}}
        assert methode_depuis_parametres(entreprise) == METHODE_SALAIRE_RETABLI

    def test_une_valeur_inconnue_vaut_le_defaut(self):
        entreprise = {"parametres_paie": {"indemnite_cp_fin_cdd": "quadra"}}
        assert methode_depuis_parametres(entreprise) == METHODE_PAR_DEFAUT


class TestSalaireRetabli:
    def test_demory_39_h_a_12_31(self):
        # 151,67 h × 12,31 = 1 867,06 ; 17,33 h × 15,3875 = 266,67
        assert salaire_retabli_du_mois(12.31, 39.0, 0.25) == pytest.approx(2133.73)

    def test_a_35_h_pas_de_structurelles(self):
        assert salaire_retabli_du_mois(12.31, 35.0, 0.25) == pytest.approx(round(151.67 * 12.31, 2))

    def test_cotte_39_h_a_13_208(self):
        # 2 003,26 + 286,12 = le sous-total contractuel de son bulletin
        assert salaire_retabli_du_mois(13.208, 39.0, 0.25) == pytest.approx(2289.38)


class TestValeurJourMaintien:
    def test_demory(self):
        # 7 h × 12,31 + 0,8 h × 15,3875 = 86,17 + 12,31
        assert valeur_jour_maintien(12.31, 39.0, 0.25) == pytest.approx(98.48)

    def test_a_35_h_sept_heures_de_base(self):
        assert valeur_jour_maintien(12.31, 35.0, 0.25) == pytest.approx(86.17)


class TestAssiette:
    def test_demory_au_centime(self):
        a = assiette_salaire_retabli(
            cumul_brut_contrat=6197.76,
            brut_du_mois=1772.64,
            sous_total_contractuel_reel=1772.64,
            salaire_retabli=2133.73,
            precarite=797.04,
            solde_n1_jours=2.78,
            valeur_jour=98.48,
        )
        assert a.mois_retabli == pytest.approx(2133.73)
        assert a.solde_n1_valorise == pytest.approx(273.77)
        assert a.total == pytest.approx(9402.30)
        assert round(a.total * 0.10, 2) == pytest.approx(940.23)

    def test_les_autres_elements_du_mois_restent(self):
        """Une prime de 100 dans le mois de sortie reste dans l'assiette :
        seul le sous-total contractuel est rétabli."""
        a = assiette_salaire_retabli(
            cumul_brut_contrat=6197.76,
            brut_du_mois=1872.64,
            sous_total_contractuel_reel=1772.64,
            salaire_retabli=2133.73,
            precarite=797.04,
            solde_n1_jours=2.78,
            valeur_jour=98.48,
        )
        assert a.mois_retabli == pytest.approx(2233.73)
        assert a.total == pytest.approx(9502.30)

    def test_sans_solde_n1_pas_de_brique(self):
        a = assiette_salaire_retabli(
            cumul_brut_contrat=6197.76,
            brut_du_mois=1772.64,
            sous_total_contractuel_reel=1772.64,
            salaire_retabli=2133.73,
            precarite=797.04,
            solde_n1_jours=0.0,
            valeur_jour=98.48,
        )
        assert a.solde_n1_valorise == 0.0
        assert a.total == pytest.approx(9128.53)

    def test_un_solde_negatif_ne_retire_rien(self):
        a = assiette_salaire_retabli(
            cumul_brut_contrat=6197.76,
            brut_du_mois=1772.64,
            sous_total_contractuel_reel=1772.64,
            salaire_retabli=2133.73,
            precarite=797.04,
            solde_n1_jours=-1.5,
            valeur_jour=98.48,
        )
        assert a.solde_n1_valorise == 0.0

    def test_le_detail_se_serialise(self):
        a = assiette_salaire_retabli(
            cumul_brut_contrat=6197.76, brut_du_mois=1772.64, sous_total_contractuel_reel=1772.64,
            salaire_retabli=2133.73, precarite=797.04, solde_n1_jours=2.78, valeur_jour=98.48,
        )
        d = a.resume(taux=0.10, montant=940.23)
        assert d["methode"] == METHODE_SALAIRE_RETABLI
        assert d["assiette"] == pytest.approx(9402.30)
        assert d["montant"] == pytest.approx(940.23)
        assert d["solde_n1_jours"] == 2.78 and d["valeur_jour"] == 98.48
        assert "mention" in d


class TestMention:
    def test_texte(self):
        a = assiette_salaire_retabli(
            cumul_brut_contrat=6197.76, brut_du_mois=1772.64, sous_total_contractuel_reel=1772.64,
            salaire_retabli=2133.73, precarite=797.04, solde_n1_jours=2.78, valeur_jour=98.48,
        )
        texte = mention(a, taux=0.10, montant=940.23)
        assert texte == (
            "Indemnité de congés payés de fin de CDD (méthode société : salaire rétabli du mois "
            "de sortie, congés N-1 inclus) : 6 197,76 (brut du contrat avant le mois) + 2 133,73 "
            "(mois de sortie rétabli) + 797,04 (précarité) + 273,77 (solde N-1 : 2,78 j × 98,48) "
            "= 9 402,30 × 10 % = 940,23."
        )

    def test_sans_solde_la_brique_disparait(self):
        a = assiette_salaire_retabli(
            cumul_brut_contrat=6197.76, brut_du_mois=1772.64, sous_total_contractuel_reel=1772.64,
            salaire_retabli=2133.73, precarite=797.04, solde_n1_jours=0.0, valeur_jour=98.48,
        )
        texte = mention(a, taux=0.10, montant=912.85)
        assert "solde N-1" not in texte and texte.endswith("= 9 128,53 × 10 % = 912,85.")
