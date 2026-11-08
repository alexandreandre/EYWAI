"""Flux complet notification document — chaînage commandes métier."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.modules.documents.application import commands as doc_commands
from app.modules.documents.schemas.requests import UpdateDocumentStatusRequest


class TestDocumentNotificationChain:
    def test_transmit_immediate_chains_to_notify(self):
        pdf = b"%PDF-1.4 test"
        with (
            patch.object(doc_commands, "_load_employee", return_value={"id": "emp-1"}),
            patch.object(doc_commands, "get_storage_provider") as mock_storage_factory,
            patch.object(doc_commands.documents_repository, "insert") as mock_insert,
            patch.object(doc_commands, "notify_employee_new_document") as mock_notify,
        ):
            mock_storage_factory.return_value = MagicMock()
            mock_insert.return_value = {
                "id": "doc-1",
                "employee_id": "emp-1",
                "document_type": "document_transmis",
                "generation_context": {"custom_label": "Attestation mutuelle"},
            }

            doc_commands.transmit_employee_document(
                "co-1",
                "user-rh",
                "emp-1",
                "Attestation mutuelle",
                pdf,
                "attestation.pdf",
                send_immediately=True,
            )

        mock_notify.assert_called_once_with("emp-1", "co-1", "Attestation mutuelle")

    def test_status_envoye_chains_to_notify(self):
        previous = {
            "id": "doc-1",
            "employee_id": "emp-1",
            "document_type": "attestation_emploi",
            "status": "brouillon",
            "generation_context": {},
        }
        updated = {**previous, "status": "envoye"}

        with (
            patch.object(
                doc_commands.documents_repository, "get_by_id", return_value=previous
            ),
            patch.object(
                doc_commands.documents_repository, "update_status", return_value=updated
            ),
            patch.object(doc_commands, "notify_employee_new_document") as mock_notify,
        ):
            doc_commands.update_document_status(
                "doc-1",
                "co-1",
                UpdateDocumentStatusRequest(status="envoye"),
            )

        mock_notify.assert_called_once_with("emp-1", "co-1", "Attestation d'emploi")

    def test_notify_never_raises_on_smtp_failure(self):
        from app.modules.notifications.application import employee_document_alerts as mod

        with (
            patch.object(mod, "_insert_notification", return_value=True),
            patch.object(mod, "_load_employee_contact", return_value=("a@test.com", "Bob")),
            patch.object(mod, "get_smtp_mail_sender") as sender_factory,
        ):
            sender = MagicMock()
            sender.send_multipart_email.return_value = (False, "SMTP down")
            sender_factory.return_value = sender

            mod.notify_employee_new_document("emp-1", "co-1", "Test doc")

        sender.send_multipart_email.assert_called_once()
