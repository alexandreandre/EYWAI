"""Tests de la lecture de l'état de provision du cabinet (reprise des reports)."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from scripts.reprise_soldes_cp_cabinet import parser_reports  # noqa: E402

pytestmark = pytest.mark.unit

# Rendu réel de `pdftotext -layout` sur l'état CARTOL du 21/07/2026.
# Le numéro de collaborateur occupe les 18 premières colonnes et porte parfois une
# lettre de désambiguïsation qu'il ne faut pas prendre pour un prénom.
EXTRAIT = """
                                                Solde Solde Solde       Salaire de      Taux        Montant
    Numéro             Nom de l'employé                                                                            Provision          Total
                                                jrs N-1 jrs N jours     référence      Ch. soc. Charges sociales

   BERTAUD        SYLVAIN BERTAUD                28.00   4.16   32.16       2 640.86     25.74           993.68       3 860.46             4 854.14
   COUTANT D      DENIS COUTANT                  28.00   4.16   32.16       4 097.55     45.83         2 745.16       5 989.87             8 735.03
   LEMAIRE JN     Jean-Noël LEMAIRE              21.00   4.16   25.16       1 357.34     35.45           550.29       1 552.30             2 102.59
   LEMAIRE L      LAURETTE LEMAIRE               54.00   4.16   58.16       1 355.98     20.25           725.91       3 584.72             4 310.63
   DEPLANNE       MARIE-NOELLE DEPLANNE          30.00   4.16   34.16       2 149.50     30.22         1 008.62       3 337.59             4 346.21
   Total                                       1956.50295.36 2251.86     210 447.53     32.32       102 087.17     292 034.05           394 121.22
"""


class TestParserReports:
    def test_cinq_lignes_sans_le_total(self):
        assert len(parser_reports(EXTRAIT)) == 5

    def test_numero_et_nom_ne_se_melangent_pas(self):
        par_numero = {r["numero"]: r["nom"] for r in parser_reports(EXTRAIT)}
        # « D » appartient au numéro « COUTANT D », pas au prénom
        assert par_numero["COUTANT D"] == "DENIS COUTANT"
        assert par_numero["LEMAIRE JN"] == "Jean-Noël LEMAIRE"
        assert par_numero["LEMAIRE L"] == "LAURETTE LEMAIRE"
        assert par_numero["BERTAUD"] == "SYLVAIN BERTAUD"

    def test_solde_n1_lu_et_non_le_solde_total(self):
        par_numero = {r["numero"]: r["solde_n1_ouvres"] for r in parser_reports(EXTRAIT)}
        assert par_numero["BERTAUD"] == 28.00
        assert par_numero["LEMAIRE L"] == 54.00

    def test_ligne_total_ecartee(self):
        assert all(r["numero"] != "Total" for r in parser_reports(EXTRAIT))

    def test_texte_vide(self):
        assert parser_reports("") == []
