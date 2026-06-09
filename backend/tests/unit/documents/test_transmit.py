"""Tests — transmission document RH vers espace salarié."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.modules.documents.application import commands
from app.modules.documents.infrastructure.repository import documents_repository


PDF_BYTES = b"%PDF-1.4 test content"


def _mock_employee_load():
    return patch.object(
        commands,
        "_load_employee",
        return_value={"id": "emp-1", "first_name": "Jean", "last_name": "Dupont"},
    )


@patch("app.modules.documents.application.commands._notify_document_sent_to_employee")
@patch("app.modules.documents.application.commands.documents_repository")
@patch("app.modules.documents.application.commands.get_storage_provider")
@patch.object(commands, "_load_employee")
def test_transmit_pdf_success_send_immediately(
    mock_load_employee,
    mock_get_storage,
    mock_repo,
    mock_notify,
):
    mock_load_employee.return_value = {"id": "emp-1"}
    storage = MagicMock()
    mock_get_storage.return_value = storage
    mock_repo.insert.return_value = {
        "id": "doc-1",
        "employee_id": "emp-1",
        "status": "envoye",
        "document_type": "document_transmis",
        "generation_context": {"custom_label": "Attestation mutuelle"},
    }

    row = commands.transmit_employee_document(
        "company-1",
        "user-rh",
        "emp-1",
        "Attestation mutuelle",
        PDF_BYTES,
        "attestation.pdf",
        send_immediately=True,
    )

    assert row["id"] == "doc-1"
    storage.upload.assert_called_once()
    upload_args = storage.upload.call_args[0]
    assert upload_args[0] == "generated_documents"
    assert upload_args[1].startswith("company-1/emp-1/document_transmis_")
    assert upload_args[1].endswith(".pdf")
    insert_row = mock_repo.insert.call_args[0][0]
    assert insert_row["status"] == "envoye"
    assert insert_row["document_type"] == "document_transmis"
    assert insert_row["generation_context"]["custom_label"] == "Attestation mutuelle"
    mock_notify.assert_called_once()


@patch("app.modules.documents.application.commands._notify_document_sent_to_employee")
@patch("app.modules.documents.application.commands.documents_repository")
@patch("app.modules.documents.application.commands.get_storage_provider")
@patch.object(commands, "_load_employee")
def test_transmit_pdf_brouillon_no_notification(
    mock_load_employee,
    mock_get_storage,
    mock_repo,
    mock_notify,
):
    mock_load_employee.return_value = {"id": "emp-1"}
    mock_get_storage.return_value = MagicMock()
    mock_repo.insert.return_value = {"id": "doc-2", "status": "brouillon"}

    commands.transmit_employee_document(
        "company-1",
        "user-rh",
        "emp-1",
        "Note interne",
        PDF_BYTES,
        "note.pdf",
        send_immediately=False,
    )

    insert_row = mock_repo.insert.call_args[0][0]
    assert insert_row["status"] == "brouillon"
    mock_notify.assert_not_called()


def test_transmit_rejects_non_pdf():
    with _mock_employee_load():
        with pytest.raises(ValueError, match="PDF"):
            commands.transmit_employee_document(
                "company-1",
                "user-rh",
                "emp-1",
                "Mon document",
                PDF_BYTES,
                "image.png",
            )


def test_transmit_rejects_empty_file():
    with _mock_employee_load():
        with pytest.raises(ValueError, match="vide"):
            commands.transmit_employee_document(
                "company-1",
                "user-rh",
                "emp-1",
                "Mon document",
                b"",
                "doc.pdf",
            )


def test_document_display_label_uses_custom_label():
    label = commands._document_display_label(
        {
            "document_type": "document_transmis",
            "generation_context": {"custom_label": "  Attestation mutuelle 2026 "},
        }
    )
    assert label == "Attestation mutuelle 2026"


def test_document_display_label_falls_back_to_type_label():
    label = commands._document_display_label(
        {"document_type": "attestation_emploi", "generation_context": {}}
    )
    assert label == "Attestation d'emploi"


def test_employee_can_access_status():
    assert documents_repository.employee_can_access_status("envoye") is True
    assert documents_repository.employee_can_access_status("signe") is True
    assert documents_repository.employee_can_access_status("brouillon") is False
    assert documents_repository.employee_can_access_status("archive") is False


@patch("app.modules.documents.infrastructure.repository.supabase")
def test_get_all_employee_visible_only_filters_status(mock_supabase):
    chain = MagicMock()
    mock_supabase.table.return_value = chain
    chain.select.return_value = chain
    chain.eq.return_value = chain
    chain.in_.return_value = chain
    chain.order.return_value = chain
    chain.execute.return_value = MagicMock(data=[])

    documents_repository.get_all("company-1", employee_id="emp-1", employee_visible_only=True)

    chain.in_.assert_called_once_with("status", ["envoye", "signe"])
