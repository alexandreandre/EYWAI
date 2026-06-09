"""Tests — alertes document salarié."""

from unittest.mock import MagicMock, patch

import pytest

from app.modules.notifications.application import employee_document_alerts as mod


@pytest.fixture
def mock_supabase():
    with patch("app.modules.notifications.application.employee_document_alerts.supabase") as sb:
        table = MagicMock()
        sb.table.return_value = table
        yield sb, table


class TestNotifyEmployeeNewDocument:
    def test_inserts_notification_and_sends_email(self, mock_supabase):
        sb, table = mock_supabase
        select_chain = MagicMock()
        select_chain.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
            data={"email": "alice@example.com", "first_name": "Alice"}
        )
        table.select.return_value = select_chain
        insert_chain = MagicMock()
        table.insert.return_value = insert_chain
        insert_chain.execute.return_value = MagicMock(data=[{"id": "n1"}])

        with patch.object(mod, "get_resolved_email_config") as cfg, patch.object(
            mod, "get_smtp_mail_sender"
        ) as sender_factory:
            cfg.return_value = MagicMock(frontend_url="http://localhost:8080")
            sender = MagicMock()
            sender.send_multipart_email.return_value = (True, None)
            sender_factory.return_value = sender

            mod.notify_employee_new_document("emp-1", "co-1", "Attestation d'emploi")

        table.insert.assert_called_once()
        payload = table.insert.call_args[0][0]
        assert payload["type"] == "nouveau_document"
        assert "Attestation d'emploi" in payload["message"]
        sender.send_multipart_email.assert_called_once()
        assert sender.send_multipart_email.call_args.kwargs["to_email"] == "alice@example.com"

    def test_skips_email_when_no_address(self, mock_supabase):
        sb, table = mock_supabase
        select_chain = MagicMock()
        select_chain.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
            data={"email": "", "first_name": "Bob"}
        )
        table.select.return_value = select_chain
        table.insert.return_value.execute.return_value = MagicMock(data=[{"id": "n1"}])

        with patch.object(mod, "get_smtp_mail_sender") as sender_factory:
            mod.notify_employee_new_document("emp-1", "co-1", "CDI")
            sender_factory.return_value.send_multipart_email.assert_not_called()

        table.insert.assert_called_once()


class TestUpdateDocumentStatusNotification:
    def test_notifies_when_status_becomes_envoye(self):
        from app.modules.documents.application import commands as doc_commands
        from app.modules.documents.schemas.requests import UpdateDocumentStatusRequest

        previous = {
            "id": "doc-1",
            "employee_id": "emp-1",
            "document_type": "attestation_emploi",
            "status": "brouillon",
        }
        updated = {**previous, "status": "envoye"}

        with patch.object(
            doc_commands.documents_repository, "get_by_id", return_value=previous
        ), patch.object(
            doc_commands.documents_repository, "update_status", return_value=updated
        ), patch.object(
            doc_commands, "notify_employee_new_document"
        ) as notify:
            row = doc_commands.update_document_status(
                "doc-1",
                "co-1",
                UpdateDocumentStatusRequest(status="envoye"),
            )

        assert row["status"] == "envoye"
        notify.assert_called_once_with("emp-1", "co-1", "Attestation d'emploi")

    def test_does_not_notify_when_already_envoye(self):
        from app.modules.documents.application import commands as doc_commands
        from app.modules.documents.schemas.requests import UpdateDocumentStatusRequest

        previous = {
            "id": "doc-1",
            "employee_id": "emp-1",
            "document_type": "attestation_emploi",
            "status": "envoye",
        }
        updated = {**previous, "status": "signe"}

        with patch.object(
            doc_commands.documents_repository, "get_by_id", return_value=previous
        ), patch.object(
            doc_commands.documents_repository, "update_status", return_value=updated
        ), patch.object(doc_commands, "_handle_avenant_signe"), patch.object(
            doc_commands, "notify_employee_new_document"
        ) as notify:
            doc_commands.update_document_status(
                "doc-1",
                "co-1",
                UpdateDocumentStatusRequest(status="signe"),
                updated_by_user_id="user-1",
            )

        notify.assert_not_called()
