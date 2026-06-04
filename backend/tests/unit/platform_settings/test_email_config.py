"""Tests résolution config SMTP (DB active vs repli env)."""

from unittest.mock import patch

import pytest

from app.modules.platform_settings.application import email_config
from app.modules.platform_settings.application.email_config import (
    get_resolved_email_config,
    get_support_recipients,
    invalidate_email_config_cache,
)

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _clear_cache():
    invalidate_email_config_cache()
    yield
    invalidate_email_config_cache()


class TestResolvedEmailConfig:
    def test_falls_back_to_environment_when_no_row(self):
        with patch.object(email_config.repository, "get_row", return_value=None), patch(
            "app.modules.platform_settings.application.email_config.app_settings.SMTP_USER",
            "env-user",
        ), patch(
            "app.modules.platform_settings.application.email_config.app_settings.SMTP_PASSWORD",
            "env-pass",
        ), patch(
            "app.modules.platform_settings.application.email_config.app_settings.SUPPORT_RECIPIENTS",
            ("support@eywai.fr",),
        ):
            cfg = get_resolved_email_config(force_refresh=True)
        assert cfg.source == "environment"
        assert cfg.smtp_user == "env-user"
        assert cfg.support_recipients == ("support@eywai.fr",)

    def test_uses_database_when_active(self):
        row = {
            "is_active": True,
            "smtp_host": "smtp.custom.fr",
            "smtp_port": 465,
            "smtp_user": "db-user",
            "smtp_password": "db-pass",
            "smtp_security": "ssl",
            "from_email": "noreply@eywai.fr",
            "from_name": "EYWAI Test",
            "support_recipients": ["a@eywai.fr", "b@eywai.fr"],
        }
        with patch.object(email_config.repository, "get_row", return_value=row):
            cfg = get_resolved_email_config(force_refresh=True)
        assert cfg.source == "database"
        assert cfg.smtp_host == "smtp.custom.fr"
        assert cfg.smtp_port == 465
        assert cfg.smtp_security == "ssl"
        assert cfg.support_recipients == ("a@eywai.fr", "b@eywai.fr")

    def test_inactive_row_uses_environment(self):
        row = {"is_active": False, "smtp_user": "ignored"}
        with patch.object(email_config.repository, "get_row", return_value=row), patch(
            "app.modules.platform_settings.application.email_config.app_settings.SMTP_USER",
            "env-only",
        ):
            cfg = get_resolved_email_config(force_refresh=True)
        assert cfg.source == "environment"
        assert cfg.smtp_user == "env-only"

    def test_get_support_recipients(self):
        with patch(
            "app.modules.platform_settings.application.email_config.get_resolved_email_config"
        ) as mock_cfg:
            mock_cfg.return_value.support_recipients = ("x@eywai.fr",)
            assert get_support_recipients() == ["x@eywai.fr"]
