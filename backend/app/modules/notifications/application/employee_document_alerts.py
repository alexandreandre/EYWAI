"""Notification in-app + e-mail lorsqu'un document est publié sur l'espace salarié."""

from __future__ import annotations

import html
import logging
from typing import Optional, Tuple

from app.core.database import supabase
from app.modules.platform_settings.application.email_config import get_resolved_email_config
from app.shared.infrastructure.email.smtp_sender import get_smtp_mail_sender

logger = logging.getLogger(__name__)

NOTIFICATION_TYPE = "nouveau_document"


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


def _insert_notification(employee_id: str, company_id: str, message: str) -> bool:
    try:
        supabase.table("notifications").insert(
            {
                "employee_id": employee_id,
                "company_id": company_id,
                "type": NOTIFICATION_TYPE,
                "message": message,
                "is_read": False,
            }
        ).execute()
        return True
    except Exception as exc:
        logger.info("[doc_notif] Notification non insérée pour %s: %s", employee_id, exc)
        return False


def _send_email(to_email: str, first_name: Optional[str], document_label: str) -> bool:
    sender = get_smtp_mail_sender()
    config = get_resolved_email_config()
    documents_url = f"{config.frontend_url.rstrip('/')}/employee/documents"
    greeting = f"Bonjour {first_name}," if first_name else "Bonjour,"
    esc_label = html.escape(document_label)

    text_content = f"""{greeting}

Un nouveau document est disponible dans votre espace personnel : {document_label}.

Consultez-le depuis votre espace documents :
{documents_url}

Cordialement,
L'équipe EYWAI
"""

    html_content = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
  <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
    <div style="background-color: #2563eb; color: white; padding: 20px; text-align: center; border-radius: 5px 5px 0 0;">
      <h1 style="margin: 0; font-size: 20px;">Nouveau document disponible</h1>
    </div>
    <div style="background-color: #f9fafb; padding: 30px; border: 1px solid #e5e7eb;">
      <p>{html.escape(greeting)}</p>
      <p>Un nouveau document est disponible dans votre espace personnel&nbsp;:</p>
      <p style="font-weight: bold;">{esc_label}</p>
      <p style="text-align: center; margin: 24px 0;">
        <a href="{html.escape(documents_url)}"
           style="display: inline-block; padding: 12px 24px; background-color: #2563eb; color: white; text-decoration: none; border-radius: 5px;">
          Voir mes documents
        </a>
      </p>
    </div>
    <p style="text-align: center; color: #6b7280; font-size: 12px;">Cet e-mail a été envoyé par EYWAI</p>
  </div>
</body>
</html>"""

    ok, err = sender.send_multipart_email(
        to_email=to_email,
        subject="Nouveau document disponible dans votre espace",
        text_content=text_content.strip(),
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
) -> None:
    """
    Alerte in-app + e-mail (best effort) lorsqu'un document apparaît sur l'espace salarié.
    Ne lève jamais d'exception.
    """
    label = (document_label or "Document").strip() or "Document"
    message = f'Un nouveau document est disponible : « {label} ».'
    _insert_notification(employee_id, company_id, message)

    email, first_name = _load_employee_contact(employee_id)
    if email:
        _send_email(email, first_name, label)
