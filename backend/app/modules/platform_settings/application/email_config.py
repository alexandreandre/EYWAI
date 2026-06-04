"""Résolution de la configuration SMTP effective (DB active ou repli env)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, cast

from app.core import settings as app_settings
from app.modules.platform_settings.domain.value_objects import (
    DEFAULT_SUPPORT_RECIPIENTS,
    ResolvedEmailConfig,
    SmtpSecurity,
)
from app.modules.platform_settings.infrastructure.repository import repository

_config_cache: Optional[ResolvedEmailConfig] = None


def invalidate_email_config_cache() -> None:
    global _config_cache
    _config_cache = None


def _normalize_security(value: Optional[str]) -> SmtpSecurity:
    if value in ("starttls", "ssl", "none"):
        return cast(SmtpSecurity, value)
    return "starttls"


def _normalize_recipients(raw: Any) -> tuple[str, ...]:
    if isinstance(raw, list):
        cleaned = [str(x).strip() for x in raw if str(x).strip()]
        if cleaned:
            return tuple(cleaned)
    return DEFAULT_SUPPORT_RECIPIENTS


def _from_env() -> ResolvedEmailConfig:
    return ResolvedEmailConfig(
        smtp_host=app_settings.SMTP_HOST,
        smtp_port=app_settings.SMTP_PORT,
        smtp_user=app_settings.SMTP_USER,
        smtp_password=app_settings.SMTP_PASSWORD,
        smtp_security=_normalize_security(app_settings.SMTP_SECURITY),
        from_email=app_settings.FROM_EMAIL or app_settings.SMTP_USER,
        from_name=app_settings.FROM_NAME,
        reply_to=app_settings.REPLY_TO,
        support_recipients=_normalize_recipients(app_settings.SUPPORT_RECIPIENTS),
        frontend_url=app_settings.FRONTEND_URL,
        source="environment",
    )


def _from_row(row: Dict[str, Any]) -> ResolvedEmailConfig:
    return ResolvedEmailConfig(
        smtp_host=str(row.get("smtp_host") or app_settings.SMTP_HOST),
        smtp_port=int(row.get("smtp_port") or app_settings.SMTP_PORT),
        smtp_user=row.get("smtp_user") or app_settings.SMTP_USER,
        smtp_password=row.get("smtp_password") or app_settings.SMTP_PASSWORD,
        smtp_security=_normalize_security(row.get("smtp_security")),
        from_email=row.get("from_email") or row.get("smtp_user") or app_settings.FROM_EMAIL,
        from_name=str(row.get("from_name") or app_settings.FROM_NAME),
        reply_to=row.get("reply_to") or app_settings.REPLY_TO,
        support_recipients=_normalize_recipients(row.get("support_recipients")),
        frontend_url=app_settings.FRONTEND_URL,
        source="database",
    )


def get_resolved_email_config(*, force_refresh: bool = False) -> ResolvedEmailConfig:
    """Retourne la config SMTP effective (cache invalidable après mise à jour admin)."""
    global _config_cache
    if _config_cache is not None and not force_refresh:
        return _config_cache

    row = repository.get_row()
    if row and row.get("is_active"):
        _config_cache = _from_row(row)
    else:
        _config_cache = _from_env()
    return _config_cache


def get_support_recipients() -> List[str]:
    return list(get_resolved_email_config().support_recipients)
