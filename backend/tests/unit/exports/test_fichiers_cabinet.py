"""Les fichiers Quadra et Sage sont du texte : ils ne se nomment pas « .xlsx ».

Le contenu de ces deux exports est un fichier texte (ASCII à largeur fixe pour
Quadra, lignes séparées par « | » pour Sage), quel que soit le format demandé.
Un nom en « .xlsx » ne s'ouvre pas dans Excel. Le format générique reste un
vrai CSV ou un vrai classeur.
"""

import re
from unittest.mock import patch

import pytest

from app.modules.exports.application import service
from app.modules.exports.domain.formats_cabinet import nom_fichier_cabinet
from app.modules.exports.schemas import ExportGenerateRequest

pytestmark = pytest.mark.unit


class TestNomDuFichier:
    @pytest.mark.parametrize("demande", ["csv", "xlsx"])
    def test_quadra_est_un_fichier_texte(self, demande):
        assert nom_fichier_cabinet("export_cabinet_quadra", "2026-09", demande) == (
            "cabinet_quadra_2026_09.txt",
            "txt",
        )

    @pytest.mark.parametrize("demande", ["csv", "xlsx"])
    def test_sage_est_un_fichier_texte(self, demande):
        assert nom_fichier_cabinet("export_cabinet_sage", "2026-09", demande) == (
            "cabinet_sage_2026_09.txt",
            "txt",
        )

    def test_le_format_generique_garde_csv_et_xlsx(self):
        assert nom_fichier_cabinet("export_cabinet_generique", "2026-09", "xlsx") == (
            "cabinet_generique_2026_09.xlsx",
            "xlsx",
        )
        assert nom_fichier_cabinet("export_cabinet_generique", "2026-09", "csv") == (
            "cabinet_generique_2026_09.csv",
            "csv",
        )


class TestGeneration:
    def test_quadra_demande_en_xlsx_est_stocke_en_txt_comme_texte_brut(self):
        envoyes = {}

        def televerser(bucket, chemin, contenu, type_contenu):
            envoyes.update(chemin=chemin, type=type_contenu)
            return chemin

        requete = ExportGenerateRequest(
            export_type="export_cabinet_quadra", period="2026-09", format="xlsx"
        )
        with patch.object(
            service.providers, "generate_cabinet_quadra_export", return_value=b"M42100000"
        ), patch.object(service, "upload_export_file", side_effect=televerser), patch.object(
            service, "create_signed_url", return_value="https://exemple/fichier"
        ), patch.object(
            service.providers, "get_payslip_data_for_od", return_value=([], {"employees_count": 3})
        ), patch.object(service.commands, "record_export_history", return_value="exp-1"):
            reponse = service._generate_cabinet("co-1", "u-1", "Gestionnaire", requete)

        # Horodaté depuis [I16] : un export régénéré n'écrase plus le précédent.
        assert re.fullmatch(r"cabinet_quadra_2026_09_\d+\.txt", reponse.files[0].filename)
        assert reponse.files[0].format == "txt"
        assert re.search(r"/cabinet_quadra_2026_09_\d+\.txt$", envoyes["chemin"])
        assert envoyes["type"] == "text/plain"
