"""Tests unitaires — parser bulletins CP."""

from app.modules.admin_import.application.cp_payslip_parser import (
    parse_french_period,
    parse_payslip_page_text,
    parse_pdf_file,
)

BOUFRIDA_PAGE = """
   COMITECH                                                                            BULLETIN DE SALAIRE
   Z.A.la Pelissière
                                                                                         Période : Mai 2026
   01300     BELLEY                                                                      Paiement le : 31/05/26
   Siret : 49861035100013         Code NAF: 2229A                                        Du :   01/05/2026         Au :    31/05/2026

                  CP N-1         CP N
                                                                                  Mr BOUFRIDA Samir
  Acquis :         25.00 /      24.96 /
  Total pris :     25.00 /      13.00 /                                           108 Impasse Brillat Savarin
  Solde :           0.00 /      11.96 /
                                                                                  01300 BELLEY
   Matricule : BOUFRIDA              NoSécu.: 166109935323859
"""

BOUVEYRON_PAGE = """
   COMITECH                                                                            BULLETIN DE SALAIRE
   Siret : 49861035100013         Code NAF: 2229A
   Période : Mai 2026
                  CP N-1         CP N
                                                                                  Mr BOUVEYRON Michel
  Acquis :        32.50 /      26.96 /
  Total pris :    24.00 /       0.00 /
  Solde :          8.50 /      26.96 /
   Matricule : BOUVEYRON             NoSécu.: 173040103403808
        Solde repos Cadre =13j
"""

MBC_PAGE = """
   MONT BLANC COMPOSITE                                                                       BULLETIN DE SALAIRE
   1984 AVENUE DES LANDIERS
   Période : Mai 2026
   Siret : 75116833700028          Code NAF: 2229A
                 CP N-1         CP N
                                                                                        M. IBRAHIMA NDAO NGOM
  Acquis :        16.00 /      24.96 /
  Total pris :    16.00 /      13.00 /
  Solde :          0.00 /      11.96 /
   Matricule : IBRAHIMA N              NoSécu.: 173049934124273
"""

GROS_PRONIER_PAGE = """
   COMITECH                                                                            BULLETIN DE SALAIRE
   Période : Mai 2026
   Siret : 49861035100013         Code NAF: 2229A
                  CP N-1         CP N
                                                                                  MME GROS Nadine
  Acquis :        31.00 /      26.96 /
  Total pris :    25.00 /       0.00 /
  Solde :          6.00 /      26.96 /
   Matricule : GROS              NoSécu.: 263098021224031
   Nom Patronymique : PRONIER
"""

EYWAI_PAGE = """
BULLETIN DE PAIE
Solde de congés au 31/05/2026
CP période précédente
5.00 j
25.00 j
5.00 j
CP période en cours
13.00 j
2.00 j
11.00 j
SIRET : 49861035100013
"""


class TestParseFrenchPeriod:
    def test_mai_2026(self):
        year, month, label = parse_french_period("Mai 2026")
        assert year == 2026
        assert month == 5
        assert label == "Mai 2026"


class TestParseCegidClarifie:
    def test_boufrida(self):
        parsed = parse_payslip_page_text(BOUFRIDA_PAGE)
        assert parsed.parse_format == "cegid_clarifie"
        assert parsed.siret == "49861035100013"
        assert parsed.company_name == "COMITECH"
        assert parsed.cp_n1_solde == 0.0
        assert parsed.cp_n_solde == 11.96
        assert parsed.matricule == "BOUFRIDA"
        assert parsed.raw_name == "BOUFRIDA Samir"
        assert parsed.year == 2026
        assert parsed.month == 5

    def test_bouveyron_repos_cadre(self):
        parsed = parse_payslip_page_text(BOUVEYRON_PAGE)
        assert parsed.cp_n1_solde == 8.5
        assert parsed.cp_n_solde == 26.96
        assert parsed.repos_cadre_days == 13

    def test_mbc(self):
        parsed = parse_payslip_page_text(MBC_PAGE)
        assert parsed.siret == "75116833700028"
        assert parsed.company_name == "MONT BLANC COMPOSITE"
        assert parsed.matricule == "IBRAHIMA N"
        assert parsed.year == 2026
        assert parsed.month == 5
        assert parsed.period_label == "Mai 2026"
        assert parsed.cp_n1_solde == 0.0
        assert parsed.cp_n_solde == 11.96


    def test_gros_patronymic_pronier(self):
        parsed = parse_payslip_page_text(GROS_PRONIER_PAGE)
        assert parsed.matricule == "GROS"
        assert parsed.patronymic_name == "PRONIER"
        assert parsed.raw_name == "GROS Nadine"
        assert parsed.cp_n1_solde == 6.0
        assert parsed.cp_n_solde == 26.96


class TestParseEywaiNative:
    def test_solde_section(self):
        parsed = parse_payslip_page_text(EYWAI_PAGE)
        assert parsed.parse_format == "eywai_native"
        assert parsed.cp_n1_solde == 5.0
        assert parsed.cp_n_solde == 11.0
        assert parsed.year == 2026


class TestParsePdfFile:
    def test_invalid_pdf(self):
        pages, warnings = parse_pdf_file("test.pdf", b"not a pdf")
        assert pages == []
        assert warnings
