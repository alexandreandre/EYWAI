"""Chaque version d'un bulletin garde son propre PDF."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.modules.payslips.domain.historique import chemin_pdf_de_version, pdfs_sortis

pytestmark = pytest.mark.unit

CHEMIN = "co/emp/bulletins/Bulletin_X_08-2026.pdf"


def test_le_pdf_d_une_version_porte_son_numero():
    assert chemin_pdf_de_version(CHEMIN, 4) == "co/emp/bulletins/Bulletin_X_08-2026_v4.pdf"


def test_les_pdf_des_versions_sorties_du_plafond_sont_designes():
    avant = [{"version": 1, "pdf_storage_path": "a_v1.pdf"}, {"version": 2}, {"version": 3, "pdf_storage_path": "a_v3.pdf"}]
    assert pdfs_sortis(avant, avant[1:]) == ["a_v1.pdf"]


def test_l_archive_avant_regeneration_copie_le_pdf_de_la_version():
    from app.modules.payslips.application import commands
    from app.modules.payslips.application.dto import GeneratePayslipInput

    existant = {
        "id": "ps-1", "status": "brouillon", "payslip_data": {}, "url": "u",
        "pdf_storage_path": CHEMIN,
        "edit_history": [{"version": v, "pdf_storage_path": f"old_v{v}.pdf"} for v in range(1, 11)],
    }
    client = MagicMock()
    with (
        patch.object(commands, "supabase", client),
        patch("app.modules.payslips.application.impression.archiver_pdf", side_effect=lambda src, dst: dst) as archiver,
        patch("app.modules.payslips.application.impression.supprimer_pdfs") as supprimer,
    ):
        commands._archive_before_regeneration(
            existant, GeneratePayslipInput(employee_id="e", year=2026, month=8)
        )
    archiver.assert_called_once_with(CHEMIN, "co/emp/bulletins/Bulletin_X_08-2026_v11.pdf")
    ecrit = client.table.return_value.update.call_args.args[0]["edit_history"]
    assert ecrit[-1]["pdf_storage_path"] == "co/emp/bulletins/Bulletin_X_08-2026_v11.pdf"
    supprimer.assert_called_once_with(["old_v1.pdf"])


def test_une_copie_impossible_n_empeche_pas_l_archive():
    from app.modules.payslips.application import impression

    stockage = MagicMock()
    stockage.copy.side_effect = RuntimeError("stockage indisponible")
    client = MagicMock()
    client.storage.from_.return_value = stockage
    with patch.object(impression, "supabase", client):
        assert impression.archiver_pdf(CHEMIN, "x_v2.pdf") is None
        assert impression.archiver_pdf(None, "x_v2.pdf") is None


def test_l_historique_servi_porte_un_lien_frais_vers_chaque_pdf():
    from app.modules.payslips.infrastructure import queries

    historique = [
        {"version": 1, "previous_pdf_url": "https://perime", "pdf_storage_path": "a_v1.pdf"},
        {"version": 2, "previous_pdf_url": "https://perime-aussi"},
    ]
    with patch.object(queries, "create_payslip_url_maps", return_value=({"a_v1.pdf": "https://frais"}, {})):
        servi = queries.avec_liens_des_versions(historique)
    assert servi[0]["previous_pdf_url"] == "https://frais"
    assert servi[1]["previous_pdf_url"] == "https://perime-aussi"
