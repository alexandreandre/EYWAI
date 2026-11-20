"""PDF de chaque export en tableau, depuis son Excel (Elsa, 17/11)."""

import io
from unittest.mock import patch

import pytest
from openpyxl import Workbook
from PyPDF2 import PdfReader

from app.modules.exports.application import service
from app.modules.exports.infrastructure import providers
from app.shared.utils.export import generate_xlsx
from app.shared.utils import export_pdf
from app.shared.utils.export_pdf import pdf_depuis_le_classeur, texte_de_cellule, titre_du_pdf, xlsx_en_pdf

pytestmark = pytest.mark.unit


def _texte(pdf: bytes) -> str:
    return "\n".join(page.extract_text() for page in PdfReader(io.BytesIO(pdf)).pages)


class TestConvertisseur:
    def test_les_montants_a_la_francaise(self):
        assert texte_de_cellule(1234.5) == "1 234,50"
        assert texte_de_cellule(-12.0, decimales=True) == "-12,00"
        assert texte_de_cellule(5) == "5"
        assert texte_de_cellule(2500) == "2 500"
        assert texte_de_cellule(2500, decimales=True) == "2 500,00"
        assert texte_de_cellule(None) == ""

    def test_une_feuille_devient_un_tableau(self):
        xlsx = generate_xlsx(
            [{"Nom": "A", "Brut": 2500.0}, {"Nom": "B", "Brut": 1801.23}], ["Nom", "Brut"], "Journal"
        )
        pdf = xlsx_en_pdf(xlsx, "Journal de paie Octobre 2026")
        assert pdf.startswith(b"%PDF")
        texte = _texte(pdf)
        assert "Journal de paie Octobre 2026" in texte
        assert "1 801,23" in texte and "2 500,00" in texte

    def test_chaque_feuille_a_son_titre(self):
        classeur = Workbook()
        classeur.active.title = "Tableau des charges"
        classeur.active.append(["Caisse", "Montant"])
        classeur.active.append(["URSSAF", 1000.0])
        detail = classeur.create_sheet("Détail")
        detail.append(["Salarié", "Montant"])
        sortie = io.BytesIO()
        classeur.save(sortie)
        texte = _texte(xlsx_en_pdf(sortie.getvalue(), "Charges"))
        assert "Charges — Tableau des charges" in texte
        assert "Charges — Détail" in texte

    def test_beaucoup_de_lignes_tiennent_sur_plusieurs_pages(self):
        lignes = [{"N": i, "Libellé": f"Ligne {i}", "Montant": i * 1.5} for i in range(300)]
        pdf = xlsx_en_pdf(generate_xlsx(lignes, ["N", "Libellé", "Montant"]), "Long")
        assert len(PdfReader(io.BytesIO(pdf)).pages) > 1


class TestDecorateur:
    def test_le_pdf_part_de_l_excel(self):
        recu = []

        @pdf_depuis_le_classeur("Essai")
        def generer(company_id, period, file_format="csv"):
            recu.append(file_format)
            if file_format == "xlsx":
                return generate_xlsx([{"A": 1}], ["A"])
            return b"A\n1\n"

        assert generer("co", "2026-10", "csv") == b"A\n1\n"
        with patch.object(export_pdf, "nom_de_la_societe", return_value=""):
            assert generer("co", "2026-10", file_format="pdf").startswith(b"%PDF")
        assert recu == ["csv", "xlsx"]

    def test_le_titre_porte_la_societe_et_le_mois(self):
        """Un groupe a plusieurs sociétés : le PDF dit de laquelle il parle (Elsa, 20/11)."""

        @pdf_depuis_le_classeur("Journal de paie")
        def generer(company_id, period, format="csv"):
            return generate_xlsx([{"A": 1}], ["A"])

        with patch.object(export_pdf, "nom_de_la_societe", return_value="Société Exemple") as lecture:
            texte = _texte(generer("co-7", "2026-10", format="pdf"))
        lecture.assert_called_once_with("co-7")
        assert "Journal de paie — Société Exemple — Octobre 2026" in texte

    def test_sans_nom_de_societe_le_titre_reste_lisible(self):
        assert titre_du_pdf("Journal de paie", "", "Octobre 2026") == "Journal de paie — Octobre 2026"
        assert titre_du_pdf("OD", "  ", "") == "OD"

    def test_le_csv_ne_lit_pas_la_societe(self):
        @pdf_depuis_le_classeur("Essai")
        def generer(company_id, period, format="csv"):
            return b"A\n1\n"

        with patch.object(export_pdf, "nom_de_la_societe") as lecture:
            generer("co", "2026-10", "csv")
        lecture.assert_not_called()

    def test_l_od_recoit_la_societe_pour_son_titre(self):
        ecritures = [
            {
                "date_ecriture": "2026-10-31",
                "journal": "OD",
                "compte_comptable": "421",
                "libelle": "Net",
                "debit": 0.0,
                "credit": 100.0,
                "periode_paie": "2026-10",
            }
        ]
        with patch.object(export_pdf, "nom_de_la_societe", return_value="Société Exemple"):
            pdf = providers.generate_od_export_file(
                ecritures, "od_globale", "2026-10", "pdf", company_id="co-7"
            )
        assert "Société Exemple" in _texte(pdf)

    def test_la_facade_des_exports_porte_le_decorateur(self):
        for nom in ("generate_journal_paie_export", "generate_charges_sociales_export", "generate_od_export_file"):
            assert hasattr(getattr(providers, nom), "__wrapped__"), nom


class TestService:
    def test_un_fichier_a_format_impose_refuse_le_pdf(self):
        from app.modules.exports.schemas.requests import ExportGenerateRequest

        for type_ in ("dsn_mensuelle", "fec", "export_cabinet_quadra"):
            requete = ExportGenerateRequest(export_type=type_, period="2026-10", format="pdf")
            with pytest.raises(ValueError, match="ne sort pas en PDF"):
                service.generate_export("co-1", "u-1", requete)

    def test_type_de_contenu(self):
        assert service._content_type("pdf") == "application/pdf"


class TestRelecture:
    def test_un_chevron_dans_un_libelle_ne_casse_pas_le_pdf(self):
        lignes = [{"Libellé": "Péage A1<A6", "Montant": 12.5}, {"Libellé": "<i>client & co", "Montant": 3.0}]
        texte = _texte(xlsx_en_pdf(generate_xlsx(lignes, ["Libellé", "Montant"]), "Notes"))
        assert "Péage A1<A6" in texte and "<i>client & co" in texte
