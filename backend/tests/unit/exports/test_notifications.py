"""Tests unitaires notifications exports."""

from unittest.mock import MagicMock, patch

from app.modules.exports.application.notifications import notify_export_recipients


class TestNotifyExportRecipients:
    def test_skipped_no_recipients(self):
        result = notify_export_recipients("co-1", [], ["exp-1"])
        assert result.status == "skipped_no_recipients"

    def test_skipped_no_smtp(self):
        cfg = MagicMock()
        cfg.is_configured = False
        with patch(
            "app.modules.platform_settings.application.email_config.get_resolved_email_config",
            return_value=cfg,
        ):
            result = notify_export_recipients(
                "co-1", ["rh@test.fr"], ["exp-1"], period="2026-05"
            )
        assert result.status == "skipped_no_smtp"

    def test_sent_when_smtp_ok(self):
        cfg = MagicMock()
        cfg.is_configured = True
        with patch(
            "app.modules.platform_settings.application.email_config.get_resolved_email_config",
            return_value=cfg,
        ), patch(
            "app.modules.exports.application.notifications._collect_export_files",
            return_value=([], []),
        ), patch(
            "app.modules.exports.application.notifications.get_smtp_mail_sender"
        ) as mock_sender:
            mock_sender.return_value.send_email_with_attachments.return_value = (True, None)
            result = notify_export_recipients(
                "co-1",
                ["rh@test.fr"],
                ["exp-1"],
                period="2026-05",
                export_type_label="Journal de paie",
            )
        assert result.status == "sent"
        assert result.sent_count == 1
