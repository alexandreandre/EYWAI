"""
Envoi d'e-mails de réinitialisation de mot de passe (SMTP).
Implémentation interne à `app` — ne dépend pas de `services/`.
"""

from __future__ import annotations

import os
import smtplib
import traceback
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional


class PasswordResetSmtpSender:
    """Service d'envoi d'e-mails pour la réinitialisation de mot de passe."""

    def __init__(self) -> None:
        self.smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_user = os.getenv("SMTP_USER")
        self.smtp_password = os.getenv("SMTP_PASSWORD")
        self.from_email = os.getenv("FROM_EMAIL", self.smtp_user)
        self.from_name = os.getenv("FROM_NAME", "SIRH - Système de Gestion RH")
        self.frontend_url = os.getenv("FRONTEND_URL", "http://localhost:8080")

    def send_password_reset_email(
        self,
        to_email: str,
        reset_token: str,
        user_name: Optional[str] = None,
    ) -> bool:
        try:
            reset_link = f"{self.frontend_url}/reset-password?token={reset_token}"

            msg = MIMEMultipart("alternative")
            msg["Subject"] = "Réinitialisation de votre mot de passe"
            msg["From"] = f"{self.from_name} <{self.from_email}>"
            msg["To"] = to_email

            text_content = f"""
Bonjour{" " + user_name if user_name else ""},

Vous avez demandé la réinitialisation de votre mot de passe.

Pour réinitialiser votre mot de passe, veuillez cliquer sur le lien suivant :
{reset_link}

Ce lien est valide pendant 1 heure.

Si vous n'avez pas demandé cette réinitialisation, vous pouvez ignorer cet e-mail.

Cordialement,
L'équipe SIRH
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

            <p>Vous avez demandé la réinitialisation de votre mot de passe pour votre compte SIRH.</p>

            <p>Pour créer un nouveau mot de passe, veuillez cliquer sur le bouton ci-dessous :</p>

            <div style="text-align: center;">
                <a href="{reset_link}" class="button">Réinitialiser mon mot de passe</a>
            </div>

            <p style="font-size: 14px; color: #6b7280;">
                Ou copiez et collez ce lien dans votre navigateur :<br>
                <a href="{reset_link}">{reset_link}</a>
            </p>

            <p><strong>Ce lien est valide pendant 1 heure.</strong></p>

            <p>Si vous n'avez pas demandé cette réinitialisation, vous pouvez ignorer cet e-mail en toute sécurité.</p>
        </div>
        <div class="footer">
            <p>Cet e-mail a été envoyé par le système SIRH</p>
            <p>Merci de ne pas répondre à cet e-mail</p>
        </div>
    </div>
</body>
</html>
"""

            part1 = MIMEText(text_content, "plain")
            part2 = MIMEText(html_content, "html")
            msg.attach(part1)
            msg.attach(part2)

            if not self.smtp_user or not self.smtp_password:
                print(
                    "⚠️  [EmailService] SMTP credentials not configured. Email not sent."
                )
                print(f"📧 [EmailService] Would have sent email to: {to_email}")
                print(f"🔗 [EmailService] Reset link: {reset_link}")
                return True

            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)

            print(f"✅ [EmailService] Password reset email sent to: {to_email}")
            return True

        except Exception as e:
            print(f"❌ [EmailService] Error sending email: {e}")
            print(traceback.format_exc())
            return False


_default_sender: PasswordResetSmtpSender | None = None


def get_password_reset_smtp_sender() -> PasswordResetSmtpSender:
    global _default_sender
    if _default_sender is None:
        _default_sender = PasswordResetSmtpSender()
    return _default_sender
