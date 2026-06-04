"""Tests transport SMTP (simulation debug vs échec explicite)."""

from unittest.mock import MagicMock, patch

import pytest

from app.modules.platform_settings.application.email_config import (
    invalidate_email_config_cache,
)
from app.modules.platform_settings.domain.value_objects import ResolvedEmailConfig
from app.shared.infrastructure.email.smtp_sender import SmtpMailSender

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _clear_cache():
    invalidate_email_config_cache()
    yield
    invalidate_email_config_cache()


def _unconfigured_config() -> ResolvedEmailConfig:
    return ResolvedEmailConfig(
        smtp_host="smtp.test",
        smtp_port=587,
        smtp_user=None,
        smtp_password=None,
        smtp_security="starttls",
        from_email=None,
        from_name="EYWAI",
        reply_to=None,
        support_recipients=("contact@eywai.fr",),
        frontend_url="http://localhost:8080",
        source="environment",
    )


class TestSmtpMailSender:
    def test_returns_false_when_unconfigured_and_require_delivery(self):
        sender = SmtpMailSender()
        with patch.object(sender, "_load_config", return_value=_unconfigured_config()):
            ok, err = sender.send_multipart_email(
                to_email="a@b.fr",
                subject="Test",
                text_content="t",
                html_content="<p>t</p>",
                require_delivery=True,
            )
        assert ok is False
        assert err is not None

    def test_simulates_in_debug_when_not_require_delivery(self):
        sender = SmtpMailSender()
        with patch.object(sender, "_load_config", return_value=_unconfigured_config()), patch(
            "app.shared.infrastructure.email.smtp_sender.is_app_debug_enabled",
            return_value=True,
        ):
            ok, err = sender.send_multipart_email(
                to_email="a@b.fr",
                subject="Test",
                text_content="t",
                html_content="<p>t</p>",
                require_delivery=False,
            )
        assert ok is True
        assert err is None

    def test_sends_when_configured(self):
        config = ResolvedEmailConfig(
            smtp_host="smtp.test",
            smtp_port=587,
            smtp_user="u",
            smtp_password="p",
            smtp_security="starttls",
            from_email="from@eywai.fr",
            from_name="EYWAI",
            reply_to=None,
            support_recipients=("contact@eywai.fr",),
            frontend_url="http://localhost:8080",
            source="database",
        )
        sender = SmtpMailSender()
        mock_server = MagicMock()
        mock_cm = MagicMock()
        mock_cm.__enter__.return_value = mock_server
        mock_cm.__exit__.return_value = False
        with patch.object(sender, "_load_config", return_value=config), patch.object(
            sender, "_connect", return_value=mock_cm
        ):
            ok, err = sender.send_multipart_email(
                to_email="a@b.fr",
                subject="Test",
                text_content="t",
                html_content="<p>t</p>",
            )
        assert ok is True
        assert err is None
