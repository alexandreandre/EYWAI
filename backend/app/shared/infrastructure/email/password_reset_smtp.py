"""
Compatibilité : délègue au transport SMTP partagé (smtp_sender).
"""

from __future__ import annotations

from typing import Optional

from app.shared.infrastructure.email.smtp_sender import (
    SmtpMailSender,
    get_password_reset_smtp_sender,
    get_smtp_mail_sender,
)

# Alias historique
PasswordResetSmtpSender = SmtpMailSender

__all__ = [
    "PasswordResetSmtpSender",
    "get_password_reset_smtp_sender",
    "get_smtp_mail_sender",
]
