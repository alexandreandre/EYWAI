"""E-mails ticket support — transport SMTP partagé avec la réinitialisation mot de passe."""

from __future__ import annotations
from app.core.logging import get_logger, log_app_debug

logger = get_logger("modules.support.infrastructure.email_service")

import html
import traceback
from datetime import datetime, timezone

from app.shared.infrastructure.email.password_reset_smtp import (
    get_password_reset_smtp_sender,
)


def send_support_ticket_email(
    ticket_data: dict,
    user_email: str,
    user_name: str,
    company_name: str,
) -> bool:
    """
    Envoie deux emails :
    1. Vers contact@eywai.fr avec le ticket structuré.
    2. Confirmation vers user_email avec le récapitulatif.
    Retourne True si les deux réussissent, False sinon. Ne lève jamais d'exception.
    """
    try:
        MODULES_PRIORITAIRES = [
            "Paie & Bulletins",
            "Sorties de salarié",
            "Saisies & Avances",
        ]

        urgency_labels = {
            "critique": "Critique",
            "elevee": "Élevée",
            "normale": "Normale",
            "faible": "Faible",
        }
        urgency_label = urgency_labels.get(
            ticket_data.get("urgency", ""), ticket_data.get("urgency", "")
        )
        module = ticket_data.get("module", "")
        prefix = "[PRIORITAIRE] " if module in MODULES_PRIORITAIRES else ""
        subject_support = (
            f"{prefix}[SUPPORT EYWAI] {module} — {urgency_label} — {company_name}"
        )

        now_iso = datetime.now(timezone.utc).isoformat()
        request_type = ticket_data.get("request_type", "")
        description = ticket_data.get("description", "")
        context_raw = ticket_data.get("context")
        context_line = (
            context_raw.strip()
            if isinstance(context_raw, str) and context_raw.strip()
            else None
        )

        esc_module = html.escape(str(module))
        esc_request = html.escape(str(request_type))
        esc_urgency = html.escape(str(urgency_label))
        esc_description = html.escape(str(description))
        esc_context = html.escape(context_line) if context_line else None
        esc_user_name = html.escape(str(user_name))
        esc_user_email = html.escape(str(user_email))
        esc_company = html.escape(str(company_name))
        esc_now = html.escape(now_iso)

        context_block_txt = (
            f"\nContexte :\n{context_line}\n"
            if context_line
            else "\nContexte : (non renseigné)\n"
        )
        context_block_html = (
            f"<p><strong>Contexte :</strong><br>{esc_context}</p>"
            if esc_context
            else "<p><strong>Contexte :</strong> (non renseigné)</p>"
        )

        text_support = f"""
Nouveau ticket support EYWAI

Date et heure (UTC) : {now_iso}
Entreprise : {company_name}
Utilisateur : {user_name}
E-mail utilisateur : {user_email}

Module : {module}
Type de demande : {request_type}
Urgence : {urgency_label}
{context_block_txt}
Description :
{description}
""".strip()

        html_support = f"""
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
            <h1>Nouveau ticket support</h1>
        </div>
        <div class="content">
            <p><strong>Date et heure (UTC) :</strong> {esc_now}</p>
            <p><strong>Entreprise :</strong> {esc_company}</p>
            <p><strong>Utilisateur :</strong> {esc_user_name}</p>
            <p><strong>E-mail utilisateur :</strong> {esc_user_email}</p>
            <p><strong>Module :</strong> {esc_module}</p>
            <p><strong>Type de demande :</strong> {esc_request}</p>
            <p><strong>Urgence :</strong> {esc_urgency}</p>
            {context_block_html}
            <p><strong>Description :</strong></p>
            <p style="white-space: pre-wrap;">{esc_description}</p>
        </div>
        <div class="footer">
            <p>Message généré par le système EYWAI</p>
        </div>
    </div>
</body>
</html>
"""

        subject_confirm = "[EYWAI] Votre demande de support a bien été reçue"

        text_confirm = f"""
Bonjour {user_name},

Nous avons bien reçu votre demande de support enregistrée le {now_iso} (UTC).

Récapitulatif :
- Entreprise : {company_name}
- Module : {module}
- Type de demande : {request_type}
- Urgence : {urgency_label}
{f"- Contexte : {context_line}" if context_line else ""}
- Description :
{description}

Notre équipe traite les demandes sous 24 à 48 heures ouvrées. Vous recevrez une réponse à l'adresse {user_email}.

Cordialement,
L'équipe EYWAI
""".strip()

        context_confirm_html = (
            f"<p><strong>Contexte :</strong> {esc_context}</p>" if esc_context else ""
        )

        html_confirm = f"""
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
            <h1>Demande reçue</h1>
        </div>
        <div class="content">
            <p>Bonjour {esc_user_name},</p>
            <p>Nous avons bien reçu votre demande de support enregistrée le <strong>{esc_now}</strong> (UTC).</p>
            <p><strong>Récapitulatif :</strong></p>
            <ul>
                <li><strong>Entreprise :</strong> {esc_company}</li>
                <li><strong>Module :</strong> {esc_module}</li>
                <li><strong>Type de demande :</strong> {esc_request}</li>
                <li><strong>Urgence :</strong> {esc_urgency}</li>
            </ul>
            {context_confirm_html}
            <p><strong>Description :</strong></p>
            <p style="white-space: pre-wrap;">{esc_description}</p>
            <p>Notre équipe traite les demandes sous <strong>24 à 48 heures ouvrées</strong>.
            Vous recevrez une réponse à l'adresse {esc_user_email}.</p>
            <p>Cordialement,<br>L'équipe EYWAI</p>
        </div>
        <div class="footer">
            <p>Cet e-mail a été envoyé par le système EYWAI</p>
        </div>
    </div>
</body>
</html>
"""

        sender = get_password_reset_smtp_sender()
        ok_support = sender.send_multipart_email(
            to_email="contact@eywai.fr",
            subject=subject_support,
            text_content=text_support,
            html_content=html_support,
        )
        ok_user = sender.send_multipart_email(
            to_email=user_email,
            subject=subject_confirm,
            text_content=text_confirm,
            html_content=html_confirm,
        )
        return bool(ok_support and ok_user)
    except Exception:
        logger.warning(f'❌ [EmailService] send_support_ticket_email: {traceback.format_exc()}')
        return False
