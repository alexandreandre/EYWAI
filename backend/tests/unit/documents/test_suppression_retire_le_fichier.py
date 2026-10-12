"""Supprimer un document généré retire aussi son fichier du stockage.

`DELETE /api/documents/<id>` supprimait la ligne de `generated_documents` et
laissait le PDF (et le Word) dans le bucket `generated_documents`, sans plus
rien qui y mène. La suppression d'un document de sortie retire déjà son
fichier ; celle d'un document généré fait de même.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.modules.documents.infrastructure import repository as depot

pytestmark = pytest.mark.unit


def _supabase(ligne):
    sb = MagicMock()
    lecture = (
        sb.table.return_value.select.return_value.eq.return_value.eq.return_value
        .maybe_single.return_value.execute.return_value
    )
    lecture.data = ligne
    return sb


def test_le_pdf_et_le_word_quittent_le_stockage():
    sb = _supabase(
        {"id": "doc-1", "file_url": "c-1/e-1/attestation.pdf", "docx_file_url": "c-1/e-1/attestation.docx"}
    )
    with patch.object(depot, "supabase", sb):
        depot.documents_repository.delete("doc-1", "c-1")

    sb.storage.from_.assert_called_with("generated_documents")
    sb.storage.from_.return_value.remove.assert_called_once_with(
        ["c-1/e-1/attestation.pdf", "c-1/e-1/attestation.docx"]
    )
    sb.table.return_value.delete.assert_called_once()


def test_une_adresse_externe_ou_un_document_sans_fichier_ne_touche_pas_au_stockage():
    sb = _supabase({"id": "doc-1", "file_url": "https://exemple.invalid/doc.pdf", "docx_file_url": None})
    with patch.object(depot, "supabase", sb):
        depot.documents_repository.delete("doc-1", "c-1")

    sb.storage.from_.return_value.remove.assert_not_called()
    sb.table.return_value.delete.assert_called_once()


def test_un_echec_du_stockage_n_empeche_pas_la_suppression():
    sb = _supabase({"id": "doc-1", "file_url": "c-1/e-1/attestation.pdf"})
    sb.storage.from_.return_value.remove.side_effect = RuntimeError("stockage indisponible")
    with patch.object(depot, "supabase", sb):
        depot.documents_repository.delete("doc-1", "c-1")

    sb.table.return_value.delete.assert_called_once()


def test_document_introuvable():
    sb = _supabase(None)
    with patch.object(depot, "supabase", sb), pytest.raises(LookupError):
        depot.documents_repository.delete("doc-x", "c-1")
    sb.storage.from_.return_value.remove.assert_not_called()
