"""Tests service configuration e-mail plateforme."""

from unittest.mock import patch

import pytest

from app.modules.platform_settings.application import service
from app.modules.platform_settings.application.email_config import (
    invalidate_email_config_cache,
)
from app.modules.platform_settings.schemas.requests import EmailSettingsUpdate

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _clear_cache():
    invalidate_email_config_cache()
    yield
    invalidate_email_config_cache()


class TestGetEmailSettings:
    def test_empty_when_no_row(self):
        with patch.object(service.repository, "get_row", return_value=None), patch(
            "app.modules.platform_settings.application.service.get_resolved_email_config"
        ) as mock_resolved:
            mock_resolved.return_value.is_configured = False
            mock_resolved.return_value.source = "environment"
            resp = service.get_email_settings()
        assert resp.is_active is False
        assert resp.has_smtp_password is False
        assert "contact@eywai.fr" in resp.support_recipients

    def test_never_exposes_password(self):
        row = {
            "smtp_password": "secret123",
            "smtp_user": "user",
            "is_active": True,
            "smtp_port": 587,
            "from_name": "EYWAI",
            "support_recipients": ["contact@eywai.fr"],
            "updated_at": "2026-01-01T00:00:00Z",
        }
        with patch.object(service.repository, "get_row", return_value=row), patch(
            "app.modules.platform_settings.application.service.get_resolved_email_config"
        ) as mock_resolved:
            mock_resolved.return_value.is_configured = True
            mock_resolved.return_value.source = "database"
            resp = service.get_email_settings()
        assert resp.has_smtp_password is True
        dumped = resp.model_dump()
        assert "smtp_password" not in dumped


class TestUpdateEmailSettings:
    def test_partial_update_preserves_password_when_omitted(self):
        captured = {}

        def fake_upsert(fields):
            captured.update(fields)
            return {
                **fields,
                "is_active": True,
                "smtp_port": 587,
                "from_name": "EYWAI",
                "support_recipients": ["contact@eywai.fr"],
            }

        with patch.object(service.repository, "get_row", return_value={"smtp_password": "old"}), patch.object(
            service.repository, "upsert", side_effect=fake_upsert
        ), patch(
            "app.modules.platform_settings.application.service.get_resolved_email_config"
        ) as mock_resolved:
            mock_resolved.return_value.is_configured = True
            mock_resolved.return_value.source = "database"
            service.update_email_settings(
                EmailSettingsUpdate(from_email="noreply@eywai.fr"),
                updated_by="admin-1",
            )
        assert "smtp_password" not in captured
        assert captured.get("from_email") == "noreply@eywai.fr"
        assert captured.get("updated_by") == "admin-1"

    def test_updates_password_when_provided(self):
        captured = {}

        def fake_upsert(fields):
            captured.update(fields)
            return {
                **fields,
                "is_active": True,
                "smtp_port": 587,
                "from_name": "EYWAI",
                "support_recipients": ["contact@eywai.fr"],
            }

        with patch.object(service.repository, "get_row", return_value=None), patch.object(
            service.repository, "upsert", side_effect=fake_upsert
        ), patch(
            "app.modules.platform_settings.application.service.get_resolved_email_config"
        ) as mock_resolved:
            mock_resolved.return_value.is_configured = True
            mock_resolved.return_value.source = "database"
            service.update_email_settings(
                EmailSettingsUpdate(smtp_password="new-secret"),
            )
        assert captured.get("smtp_password") == "new-secret"

    def test_empty_support_recipients_raises(self):
        with pytest.raises(ValueError, match="destinataire"):
            service.update_email_settings(
                EmailSettingsUpdate(support_recipients=[]),
            )


class TestSendTestEmail:
    def test_success_message(self):
        with patch(
            "app.modules.platform_settings.application.service.SmtpMailSender"
        ) as mock_cls:
            mock_cls.return_value.send_multipart_email.return_value = (True, None)
            result = service.send_test_email("test@eywai.fr")
        assert result.success is True
        assert "test@eywai.fr" in result.message

    def test_failure_message(self):
        with patch(
            "app.modules.platform_settings.application.service.SmtpMailSender"
        ) as mock_cls:
            mock_cls.return_value.send_multipart_email.return_value = (
                False,
                "Connexion refusée",
            )
            result = service.send_test_email("test@eywai.fr")
        assert result.success is False
        assert "Connexion refusée" in result.message
