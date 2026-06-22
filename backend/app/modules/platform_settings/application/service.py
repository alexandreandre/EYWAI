"""Cas d'usage — configuration e-mail plateforme."""

from __future__ import annotations

from typing import Any, Dict, Optional

from app.modules.platform_settings.application.email_config import (
    get_resolved_email_config,
    invalidate_email_config_cache,
)
from app.modules.platform_settings.domain.value_objects import DEFAULT_SUPPORT_RECIPIENTS
from app.modules.platform_settings.infrastructure.repository import repository
from app.modules.platform_settings.schemas.requests import EmailSettingsUpdate
from app.modules.platform_settings.schemas.responses import (
    EmailSettingsResponse,
    EmailTestResponse,
)


def _row_to_response(row: Optional[Dict[str, Any]]) -> EmailSettingsResponse:
    resolved = get_resolved_email_config(force_refresh=True)
    if row:
        recipients = row.get("support_recipients") or list(DEFAULT_SUPPORT_RECIPIENTS)
        return EmailSettingsResponse(
            smtp_host=row.get("smtp_host"),
            smtp_port=int(row.get("smtp_port") or 587),
            smtp_user=row.get("smtp_user"),
            has_smtp_password=bool(row.get("smtp_password")),
            smtp_security=row.get("smtp_security") or "starttls",
            from_email=row.get("from_email"),
            from_name=str(row.get("from_name") or "EYWAI"),
            reply_to=row.get("reply_to"),
            support_recipients=list(recipients),
            is_active=bool(row.get("is_active")),
            is_configured=resolved.is_configured,
            effective_source="database" if row.get("is_active") else "environment",
            updated_at=row.get("updated_at"),
        )
    return EmailSettingsResponse(
        smtp_host=None,
        smtp_port=587,
        smtp_user=None,
        has_smtp_password=False,
        smtp_security="starttls",
        from_email=None,
        from_name="EYWAI",
        reply_to=None,
        support_recipients=list(DEFAULT_SUPPORT_RECIPIENTS),
        is_active=False,
        is_configured=resolved.is_configured,
        effective_source=resolved.source if resolved.is_configured else "none",
        updated_at=None,
    )


def get_email_settings() -> EmailSettingsResponse:
    return _row_to_response(repository.get_row())


def update_email_settings(
    body: EmailSettingsUpdate,
    updated_by: Optional[str] = None,
) -> EmailSettingsResponse:
    existing = repository.get_row()
    fields: Dict[str, Any] = {}

    for key in (
        "smtp_host",
        "smtp_port",
        "smtp_user",
        "smtp_security",
        "from_email",
        "from_name",
        "reply_to",
        "is_active",
    ):
        value = getattr(body, key, None)
        if value is not None:
            fields[key] = value

    if body.support_recipients is not None:
        cleaned = [e.strip() for e in body.support_recipients if e and e.strip()]
        if not cleaned:
            raise ValueError("Au moins un destinataire support est requis.")
        fields["support_recipients"] = cleaned

    if body.smtp_password is not None and body.smtp_password.strip():
        fields["smtp_password"] = body.smtp_password.strip()

    if updated_by:
        fields["updated_by"] = updated_by

    # Activation implicite dès qu'une config exploitable est enregistrée depuis l'admin.
    if body.is_active is None and (
        fields.get("smtp_user")
        or fields.get("smtp_password")
        or fields.get("from_email")
    ):
        fields["is_active"] = True

    if not existing and not fields.get("support_recipients"):
        fields["support_recipients"] = list(DEFAULT_SUPPORT_RECIPIENTS)

    row = repository.upsert(fields)
    invalidate_email_config_cache()
    return _row_to_response(row)


def send_test_email(to_email: str) -> EmailTestResponse:
    from app.shared.infrastructure.email.smtp_sender import SmtpMailSender

    sender = SmtpMailSender()
    subject = "[EYWAI] Test de configuration e-mail"
    text = (
        "Ceci est un e-mail de test envoyé depuis l'administration EYWAI.\n\n"
        "Si vous recevez ce message, la configuration SMTP est opérationnelle."
    )
    html = (
        "<p>Ceci est un e-mail de test envoyé depuis l'<strong>administration EYWAI</strong>.</p>"
        "<p>Si vous recevez ce message, la configuration SMTP est opérationnelle.</p>"
    )
    ok, err = sender.send_multipart_email(
        to_email=to_email.strip(),
        subject=subject,
        text_content=text,
        html_content=html,
        require_delivery=True,
    )
    if ok:
        return EmailTestResponse(
            success=True,
            message=f"E-mail de test envoyé à {to_email}.",
        )
    return EmailTestResponse(
        success=False,
        message=err or "Échec de l'envoi du mail de test.",
    )
