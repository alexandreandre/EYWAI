"""Notification in-app + e-mail lorsqu'un document est publié sur l'espace salarié."""

from __future__ import annotations

import html
import logging
from typing import Optional, Tuple

from app.core.database import supabase
from app.core.settings import PAYSLIP_EMAIL_REDIRECT
from app.modules.employees.domain.rules import is_dsn_import_placeholder_email
from app.modules.platform_settings.application.email_config import get_resolved_email_config
from app.shared.infrastructure.email.smtp_sender import get_smtp_mail_sender

logger = logging.getLogger(__name__)

NOTIFICATION_TYPE = "nouveau_document"
NOTIFICATION_TYPE_PAYSLIP = "nouveau_bulletin"


def _load_employee_contact(employee_id: str) -> Tuple[Optional[str], Optional[str]]:
    """Retourne (email, prénom) du salarié (best effort)."""
    try:
        r = (
            supabase.table("employees")
            .select("email, first_name")
            .eq("id", employee_id)
            .maybe_single()
            .execute()
        )
        if not r or not r.data:
            return None, None
        email = str(r.data.get("email") or "").strip() or None
        first_name = str(r.data.get("first_name") or "").strip() or None
        return email, first_name
    except Exception as exc:
        logger.info("[doc_notif] Contact employé indisponible %s: %s", employee_id, exc)
        return None, None


def _insert_notification(
    employee_id: str,
    company_id: str,
    message: str,
    notification_type: str = NOTIFICATION_TYPE,
) -> bool:
    try:
        supabase.table("notifications").insert(
            {
                "employee_id": employee_id,
                "company_id": company_id,
                "type": notification_type,
                "message": message,
                "is_read": False,
            }
        ).execute()
        return True
    except Exception as exc:
        logger.info("[doc_notif] Notification non insérée pour %s: %s", employee_id, exc)
        return False


def _build_page_url(frontend_url: str, page_path: str) -> str:
    base = frontend_url.rstrip("/")
    path = page_path.strip().lstrip("/")
    return f"{base}/{path}" if path else base


def _email_content_for_type(
    notification_type: str,
    document_label: str,
    page_url: str,
    greeting: str,
) -> tuple[str, str, str, str]:
    """Retourne (sujet, intro texte, CTA texte, titre HTML)."""
    esc_label = html.escape(document_label)
    esc_greeting = html.escape(greeting)
    esc_url = html.escape(page_url)

    if notification_type == NOTIFICATION_TYPE_PAYSLIP:
        subject = "Nouveau bulletin de paie disponible"
        title = "Nouveau bulletin de paie"
        intro = "Votre bulletin de paie est disponible dans votre espace personnel :"
        cta = "Voir mes bulletins"
        text_intro = f"Votre bulletin de paie est disponible : {document_label}."
        text_cta_line = "Consultez-le depuis vos bulletins :"
    else:
        subject = "Nouveau document disponible dans votre espace"
        title = "Nouveau document disponible"
        intro = "Un nouveau document est disponible dans votre espace personnel :"
        cta = "Voir mes documents"
        text_intro = f"Un nouveau document est disponible : {document_label}."
        text_cta_line = "Consultez-le depuis votre espace documents :"

    text_content = f"""{greeting}

{text_intro}

{text_cta_line}
{page_url}

Cordialement,
L'équipe EYWAI
"""

    html_content = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
  <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
    <div style="background-color: #2563eb; color: white; padding: 20px; text-align: center; border-radius: 5px 5px 0 0;">
      <h1 style="margin: 0; font-size: 20px;">{html.escape(title)}</h1>
    </div>
    <div style="background-color: #f9fafb; padding: 30px; border: 1px solid #e5e7eb;">
      <p>{esc_greeting}</p>
      <p>{html.escape(intro)}</p>
      <p style="font-weight: bold;">{esc_label}</p>
      <p style="text-align: center; margin: 24px 0;">
        <a href="{esc_url}"
           style="display: inline-block; padding: 12px 24px; background-color: #2563eb; color: white; text-decoration: none; border-radius: 5px;">
          {html.escape(cta)}
        </a>
      </p>
    </div>
    <p style="text-align: center; color: #6b7280; font-size: 12px;">Cet e-mail a été envoyé par EYWAI</p>
  </div>
</body>
</html>"""

    return subject, text_content.strip(), html_content, cta


def _send_email(
    to_email: str,
    first_name: Optional[str],
    document_label: str,
    page_path: str = "employee/documents",
    notification_type: str = NOTIFICATION_TYPE,
    *,
    subject_prefix: Optional[str] = None,
) -> bool:
    sender = get_smtp_mail_sender()
    config = get_resolved_email_config()
    page_url = _build_page_url(config.frontend_url, page_path)
    greeting = f"Bonjour {first_name}," if first_name else "Bonjour,"

    subject, text_content, html_content, _cta = _email_content_for_type(
        notification_type,
        document_label,
        page_url,
        greeting,
    )
    if subject_prefix:
        subject = f"{subject_prefix} {subject}"

    ok, err = sender.send_multipart_email(
        to_email=to_email,
        subject=subject,
        text_content=text_content,
        html_content=html_content,
        require_delivery=False,
    )
    if not ok and err:
        logger.warning("[doc_notif] E-mail non envoyé à %s: %s", to_email, err)
    return ok


def notify_employee_new_document(
    employee_id: str,
    company_id: str,
    document_label: str,
    *,
    page_path: str = "employee/documents",
    notification_type: str = NOTIFICATION_TYPE,
) -> None:
    """
    Alerte in-app + e-mail (best effort) lorsqu'un document apparaît sur l'espace salarié.
    Ne lève jamais d'exception.
    """
    label = (document_label or "Document").strip() or "Document"
    if notification_type == NOTIFICATION_TYPE_PAYSLIP:
        message = f'Votre bulletin de paie est disponible : « {label} ».'
    else:
        message = f'Un nouveau document est disponible : « {label} ».'
    _insert_notification(employee_id, company_id, message, notification_type)

    email, first_name = _load_employee_contact(employee_id)
    subject_prefix = None
    if notification_type == NOTIFICATION_TYPE_PAYSLIP and PAYSLIP_EMAIL_REDIRECT:
        intended = email or "?"
        email = PAYSLIP_EMAIL_REDIRECT
        subject_prefix = f"[dest. {intended}]"
        logger.info(
            "[doc_notif] Bulletin redirigé vers %s (dest. prévue %s)",
            email,
            intended,
        )

    if not email:
        logger.warning(
            "[doc_notif] Salarié %s (société %s) sans adresse e-mail : « %s » notifié "
            "en in-app uniquement",
            employee_id,
            company_id,
            label,
        )
    elif is_dsn_import_placeholder_email(email):
        # Adresse fabriquée par la plateforme : le domaine n'est pas routable. Envoyer
        # produirait un échec SMTP silencieux et laisserait croire le salarié notifié.
        logger.warning(
            "[doc_notif] Salarié %s (société %s) : adresse fabriquée %s, aucun envoi "
            "pour « %s ». Adresse réelle à collecter.",
            employee_id,
            company_id,
            email,
            label,
        )
    else:
        _send_email(
            email,
            first_name,
            label,
            page_path=page_path,
            notification_type=notification_type,
            subject_prefix=subject_prefix,
        )
