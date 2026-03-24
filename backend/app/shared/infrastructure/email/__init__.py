# Envoi d'e-mails (app/shared) — implémentation SMTP interne à `app`.

from __future__ import annotations

from typing import Optional

from app.shared.infrastructure.email.password_reset_smtp import (
    get_password_reset_smtp_sender,
)


def send_password_reset_email(
    to_email: str,
    reset_token: str,
    user_name: Optional[str] = None,
) -> bool:
    """Envoie l'e-mail de réinitialisation de mot de passe (SMTP, variables d'environnement)."""
    return get_password_reset_smtp_sender().send_password_reset_email(
        to_email=to_email,
        reset_token=reset_token,
        user_name=user_name,
    )
