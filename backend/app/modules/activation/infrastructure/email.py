"""
E-mail d'invitation à l'activation du compte.

Contenu sobre EYWAI, texte + HTML. Le lien pointe sur
{FRONTEND_URL}/activation?token=… — le jeton en clair ne vit que dans cet
e-mail. Aucune mention d'aucun mécanisme technique interne.

Levée CIBLÉE du redirect global (EMAIL_FORCE_REDIRECT_TO) : uniquement si
le destinataire figure, à l'adresse exacte près, dans
ACTIVATION_EMAIL_ALLOWLIST. Sinon flux normal — donc redirigé en prod.
"""

from __future__ import annotations

from app.core import settings
from app.core.logging import get_logger
from app.modules.activation.domain.rules import (
    TOKEN_VALIDITY_DAYS,
    is_direct_delivery_allowed,
    parse_email_allowlist,
)
from app.shared.infrastructure.email.smtp_sender import get_smtp_mail_sender

logger = get_logger("modules.activation.email")


def build_activation_link(raw_token: str) -> str:
    base = (settings.FRONTEND_URL or "").rstrip("/")
    return f"{base}/activation?token={raw_token}"


def _build_contents(prenom: str, societe: str, link: str) -> tuple[str, str, str]:
    subject = f"Activez votre compte EYWAI — {societe}"
    text = f"""Bonjour {prenom},

{societe} vous invite à activer votre compte EYWAI, votre espace RH
personnel (bulletins de paie, absences, documents).

Pour choisir votre mot de passe, cliquez sur ce lien :
{link}

Ce lien est valide pendant {TOKEN_VALIDITY_DAYS} jours et ne peut servir qu'une fois.
Passé ce délai, demandez une nouvelle invitation à votre service RH.

Si vous n'êtes pas à l'origine de cette demande, vous pouvez ignorer cet e-mail.

Cordialement,
L'équipe EYWAI
"""
    html = f"""
<div style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
    <div style="background-color: #2563eb; color: white; padding: 20px; text-align: center; border-radius: 5px 5px 0 0;">
        <h1 style="margin: 0; font-size: 22px;">Bienvenue sur EYWAI</h1>
    </div>
    <div style="background-color: #f9fafb; padding: 30px; border: 1px solid #e5e7eb;">
        <p>Bonjour {prenom},</p>
        <p><strong>{societe}</strong> vous invite à activer votre compte EYWAI,
        votre espace RH personnel (bulletins de paie, absences, documents).</p>
        <div style="text-align: center;">
            <a href="{link}" style="display: inline-block; padding: 12px 24px; background-color: #2563eb; color: white; text-decoration: none; border-radius: 5px; margin: 20px 0;">Activer mon compte</a>
        </div>
        <p style="font-size: 14px; color: #6b7280;">
            Ou copiez ce lien :<br><a href="{link}">{link}</a>
        </p>
        <p><strong>Ce lien est valide pendant {TOKEN_VALIDITY_DAYS} jours</strong> et ne peut servir qu'une fois.
        Passé ce délai, demandez une nouvelle invitation à votre service RH.</p>
        <p style="font-size: 14px; color: #6b7280;">Si vous n'êtes pas à l'origine
        de cette demande, vous pouvez ignorer cet e-mail.</p>
    </div>
    <div style="text-align: center; padding: 20px; color: #6b7280; font-size: 12px;">
        <p>Cet e-mail a été envoyé par EYWAI</p>
    </div>
</div>
"""
    return subject, text.strip(), html


def send_activation_email(
    *,
    to_email: str,
    prenom: str,
    societe: str,
    raw_token: str,
) -> bool:
    link = build_activation_link(raw_token)
    subject, text, html = _build_contents(prenom, societe, link)

    allowlist = parse_email_allowlist(settings.ACTIVATION_EMAIL_ALLOWLIST)
    direct = is_direct_delivery_allowed(to_email, allowlist)
    if direct:
        logger.info("Invitation activation : envoi DIRECT (allowlist)")

    ok, error = get_smtp_mail_sender().send_multipart_email(
        to_email=to_email,
        subject=subject,
        text_content=text,
        html_content=html,
        bypass_forced_redirect=direct,
    )
    if not ok:
        logger.warning("Invitation activation : envoi échoué (%s)", error)
    return ok
