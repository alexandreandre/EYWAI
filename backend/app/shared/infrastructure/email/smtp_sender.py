"""
Transport SMTP partagé (reset mot de passe, support, tests admin).
Lit la configuration effective via platform_settings (DB active ou repli env).
"""

from __future__ import annotations

import smtplib
import ssl
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional, Sequence, Tuple

from app.core.logging import get_logger, is_app_debug_enabled
from app.modules.platform_settings.application.email_config import (
    get_resolved_email_config,
)
from app.modules.platform_settings.domain.value_objects import ResolvedEmailConfig

logger = get_logger("shared.email.smtp")


class SmtpMailSender:
    """Envoi d'e-mails via SMTP (config résolue à chaque envoi)."""

    def _load_config(self) -> ResolvedEmailConfig:
        return get_resolved_email_config()

    def _connect(self, config: ResolvedEmailConfig) -> smtplib.SMTP:
        if config.smtp_security == "ssl":
            server: smtplib.SMTP = smtplib.SMTP_SSL(
                config.smtp_host, config.smtp_port, timeout=30
            )
        else:
            server = smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=30)
            if config.smtp_security == "starttls":
                context = ssl.create_default_context()
                server.starttls(context=context)
        if config.smtp_user and config.smtp_password:
            server.login(config.smtp_user, config.smtp_password)
        return server

    def _handle_unconfigured(
        self,
        *,
        require_delivery: bool,
        context: str,
    ) -> Tuple[bool, Optional[str]]:
        if is_app_debug_enabled() and not require_delivery:
            logger.debug("Email simulé (%s) — SMTP non configuré", context)
            return True, None
        msg = "SMTP non configuré — impossible d'envoyer l'e-mail."
        logger.warning("%s (%s)", msg, context)
        return False, msg

    def send_email_with_attachments(
        self,
        to_emails: Sequence[str],
        subject: str,
        text_content: str,
        html_content: str,
        attachments: Sequence[tuple[str, bytes, str]],
        *,
        require_delivery: bool = False,
    ) -> Tuple[bool, Optional[str]]:
        """
        Envoie un e-mail HTML avec pièces jointes à une ou plusieurs adresses.
        Retourne (succès global, message_erreur).
        """
        recipients = [e.strip() for e in to_emails if e and e.strip()]
        if not recipients:
            return True, None

        config = self._load_config()
        if not config.is_configured:
            return self._handle_unconfigured(
                require_delivery=require_delivery,
                context=subject,
            )

        try:
            msg = MIMEMultipart("mixed")
            msg["Subject"] = subject
            msg["From"] = config.from_header
            msg["To"] = ", ".join(recipients)
            if config.reply_to:
                msg["Reply-To"] = config.reply_to

            alt = MIMEMultipart("alternative")
            alt.attach(MIMEText(text_content, "plain", "utf-8"))
            alt.attach(MIMEText(html_content, "html", "utf-8"))
            msg.attach(alt)

            for filename, content, mime_type in attachments:
                maintype, _, subtype = (mime_type or "application/octet-stream").partition(
                    "/"
                )
                part = MIMEBase(maintype, subtype or "octet-stream")
                part.set_payload(content)
                encoders.encode_base64(part)
                part.add_header(
                    "Content-Disposition",
                    "attachment",
                    filename=filename,
                )
                msg.attach(part)

            with self._connect(config) as server:
                server.send_message(msg)

            logger.info("Email avec pièces jointes envoyé à %d destinataire(s)", len(recipients))
            return True, None
        except Exception as e:
            err = f"Échec envoi e-mail avec pièces jointes : {e}"
            logger.error(err, exc_info=True)
            return False, err

    def send_multipart_email(
        self,
        to_email: str,
        subject: str,
        text_content: str,
        html_content: str,
        *,
        require_delivery: bool = False,
    ) -> Tuple[bool, Optional[str]]:
        """
        Envoie un e-mail texte + HTML.
        Retourne (succès, message_erreur).
        """
        config = self._load_config()
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = config.from_header
            msg["To"] = to_email
            if config.reply_to:
                msg["Reply-To"] = config.reply_to

            msg.attach(MIMEText(text_content, "plain", "utf-8"))
            msg.attach(MIMEText(html_content, "html", "utf-8"))

            if not config.is_configured:
                return self._handle_unconfigured(
                    require_delivery=require_delivery,
                    context=subject,
                )

            with self._connect(config) as server:
                server.send_message(msg)

            logger.info("Email envoyé")
            return True, None

        except Exception as e:
            err = f"Échec envoi e-mail : {e}"
            logger.error(err, exc_info=True)
            return False, err

    def send_password_reset_email(
        self,
        to_email: str,
        reset_token: str,
        user_name: Optional[str] = None,
    ) -> bool:
        config = self._load_config()
        reset_link = f"{config.frontend_url}/reset-password?token={reset_token}"

        text_content = f"""
Bonjour{" " + user_name if user_name else ""},

Vous avez demandé la réinitialisation de votre mot de passe.

Pour réinitialiser votre mot de passe, veuillez cliquer sur le lien suivant :
{reset_link}

Ce lien est valide pendant 1 heure.

Si vous n'avez pas demandé cette réinitialisation, vous pouvez ignorer cet e-mail.

Cordialement,
L'équipe EYWAI
"""

        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{
            font-family: Arial, sans-serif;
            line-height: 1.6;
            color: #333;
        }}
        .container {{
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
        }}
        .header {{
            background-color: #2563eb;
            color: white;
            padding: 20px;
            text-align: center;
            border-radius: 5px 5px 0 0;
        }}
        .content {{
            background-color: #f9fafb;
            padding: 30px;
            border: 1px solid #e5e7eb;
        }}
        .button {{
            display: inline-block;
            padding: 12px 24px;
            background-color: #2563eb;
            color: white;
            text-decoration: none;
            border-radius: 5px;
            margin: 20px 0;
        }}
        .footer {{
            text-align: center;
            padding: 20px;
            color: #6b7280;
            font-size: 12px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Réinitialisation de mot de passe</h1>
        </div>
        <div class="content">
            <p>Bonjour{" " + user_name if user_name else ""},</p>
            <p>Vous avez demandé la réinitialisation de votre mot de passe.</p>
            <div style="text-align: center;">
                <a href="{reset_link}" class="button">Réinitialiser mon mot de passe</a>
            </div>
            <p style="font-size: 14px; color: #6b7280;">
                Ou copiez ce lien :<br><a href="{reset_link}">{reset_link}</a>
            </p>
            <p><strong>Ce lien est valide pendant 1 heure.</strong></p>
        </div>
        <div class="footer">
            <p>Cet e-mail a été envoyé par EYWAI</p>
        </div>
    </div>
</body>
</html>
"""

        ok, _ = self.send_multipart_email(
            to_email=to_email,
            subject="Réinitialisation de votre mot de passe",
            text_content=text_content.strip(),
            html_content=html_content,
            require_delivery=False,
        )
        return ok


_default_sender: SmtpMailSender | None = None


def get_smtp_mail_sender() -> SmtpMailSender:
    global _default_sender
    if _default_sender is None:
        _default_sender = SmtpMailSender()
    return _default_sender


def get_password_reset_smtp_sender() -> SmtpMailSender:
    """Alias de compatibilité pour les imports existants."""
    return get_smtp_mail_sender()
