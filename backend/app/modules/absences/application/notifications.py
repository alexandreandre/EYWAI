"""Notifications in-app (best effort) pour le module absences."""

from __future__ import annotations

import logging
import html
from typing import Any, List

from app.core.database import supabase
from app.modules.absences.application import leave_notification_settings
from app.modules.employees.domain.rules import is_dsn_import_placeholder_email
from app.modules.platform_settings.application.email_config import (
    get_resolved_email_config,
)
from app.shared.infrastructure.email.smtp_sender import get_smtp_mail_sender

logger = logging.getLogger(__name__)

ABSENCE_TYPE_LABELS = {
    "conge_paye": "congé payé",
    "rtt": "RTT",
    "sans_solde": "congé sans solde",
    "repos_compensateur": "repos compensateur",
    "recuperation_modulation": "récupération modulation",
    "evenement_familial": "événement familial",
    "arret_maladie": "arrêt maladie",
    "arret_at": "arrêt accident du travail",
    "arret_paternite": "congé paternité",
    "arret_maternite": "congé maternité",
    "arret_maladie_pro": "maladie professionnelle",
}


def _insert_notification(
    employee_id: str,
    company_id: str,
    notif_type: str,
    message: str,
) -> None:
    """Insert best effort — ne jamais lever d'exception."""
    try:
        supabase.table("notifications").insert(
            {
                "employee_id": employee_id,
                "company_id": company_id,
                "type": notif_type,
                "message": message,
                "is_read": False,
            }
        ).execute()
    except Exception as e:
        logger.info("[absence_notif] Non insérée: %s", e)


def absence_date_range_iso(row: dict[str, Any]) -> tuple[str, str]:
    """Période (début, fin) à partir de selected_days (ISO YYYY-MM-DD)."""
    days: List[Any] = list(row.get("selected_days") or [])
    normalized: list[str] = []
    for d in days:
        if isinstance(d, str):
            normalized.append(d[:10])
        elif hasattr(d, "isoformat"):
            normalized.append(d.isoformat()[:10])
        else:
            normalized.append(str(d)[:10])
    if not normalized:
        return "—", "—"
    normalized.sort()
    return normalized[0], normalized[-1]


def employee_display_name(employee_id: str) -> str:
    """Prénom + nom pour les messages (best effort)."""
    try:
        r = (
            supabase.table("employees")
            .select("first_name, last_name")
            .eq("id", employee_id)
            .maybe_single()
            .execute()
        )
        if not r or not r.data:
            return "Un collaborateur"
        fn = (r.data.get("first_name") or "").strip()
        ln = (r.data.get("last_name") or "").strip()
        return f"{fn} {ln}".strip() or "Un collaborateur"
    except Exception:
        return "Un collaborateur"


def _employee_context(employee_id: str) -> dict[str, Any]:
    try:
        r = (
            supabase.table("employees")
            .select("first_name, last_name, email, company_id")
            .eq("id", employee_id)
            .maybe_single()
            .execute()
        )
        return r.data or {}
    except Exception:
        return {}


def _company_name(company_id: str) -> str:
    try:
        r = (
            supabase.table("companies")
            .select("company_name")
            .eq("id", company_id)
            .maybe_single()
            .execute()
        )
        if r and r.data:
            return str(r.data.get("company_name") or "Entreprise")
    except Exception:
        pass
    return "Entreprise"


def _emails_for_roles(company_id: str, roles: list[str]) -> list[str]:
    if not roles:
        return []
    try:
        access_resp = (
            supabase.table("user_company_accesses")
            .select("user_id, role")
            .eq("company_id", company_id)
            .in_("role", roles)
            .execute()
        )
        user_ids = [
            str(row.get("user_id"))
            for row in (access_resp.data or [])
            if row.get("user_id")
        ]
        if not user_ids:
            return []

        # `profiles` ne porte pas d'adresse : c'est `employees.email` qui fait
        # foi. Une lecture de `profiles.email` vivait ici et levait à chaque
        # appel, sans rien apporter — le repli ci-dessous faisait déjà tout.
        emails: list[str] = []

        try:
            employees = (
                supabase.table("employees")
                .select("user_id, email")
                .eq("company_id", company_id)
                .in_("user_id", user_ids)
                .execute()
            )
            for row in employees.data or []:
                email = str(row.get("email") or "").strip()
                if email:
                    emails.append(email)
        except Exception:
            pass
        return emails
    except Exception as exc:
        logger.info("[absence_email] Destinataires rôle non résolus: %s", exc)
        return []


def _clean_email_list(emails: list[str]) -> list[str]:
    seen: set[str] = set()
    cleaned: list[str] = []
    for raw in emails:
        email = str(raw or "").strip().lower()
        if not email or "@" not in email or is_dsn_import_placeholder_email(email):
            continue
        if email not in seen:
            cleaned.append(email)
            seen.add(email)
    return cleaned


def _resolve_leave_email_recipients(company_id: str) -> list[str]:
    settings = leave_notification_settings.get_settings(company_id)
    role_emails = _emails_for_roles(company_id, settings.recipient_roles)
    return _clean_email_list(role_emails + settings.extra_recipient_emails)


def _build_absence_action_url() -> str:
    config = get_resolved_email_config()
    return f"{config.frontend_url.rstrip('/')}/rh/absences"


def _send_leave_request_email(
    row: dict[str, Any],
    *,
    recipients: list[str],
    stage_label: str,
) -> None:
    if not recipients:
        return

    employee_id = str(row.get("employee_id") or "")
    company_id = str(row.get("company_id") or "")
    employee = _employee_context(employee_id)
    employee_name = (
        f"{employee.get('first_name') or ''} {employee.get('last_name') or ''}".strip()
        or employee_display_name(employee_id)
    )
    company_name = _company_name(company_id)
    absence_type = str(row.get("type") or "")
    absence_label = ABSENCE_TYPE_LABELS.get(absence_type, "absence")
    d0, d1 = absence_date_range_iso(row)
    days = list(row.get("selected_days") or [])
    comment = str(row.get("comment") or "").strip()
    url = _build_absence_action_url()

    subject = f"[EYWAI] Nouvelle demande de {absence_label} - {employee_name}"
    text = f"""
Nouvelle demande de {absence_label}

Entreprise : {company_name}
Salarié : {employee_name}
Période : {d0} au {d1}
Durée : {len(days)} jour(s)
Statut : {stage_label}
Commentaire : {comment or "Aucun"}

Traiter la demande : {url}
""".strip()

    esc = {
        "company": html.escape(company_name),
        "employee": html.escape(employee_name),
        "label": html.escape(absence_label),
        "d0": html.escape(d0),
        "d1": html.escape(d1),
        "stage": html.escape(stage_label),
        "comment": html.escape(comment or "Aucun"),
        "url": html.escape(url),
    }
    html_content = f"""
<!DOCTYPE html>
<html>
<body style="font-family: Arial, sans-serif; color: #1f2937; line-height: 1.5;">
  <h2>Nouvelle demande de {esc["label"]}</h2>
  <p><strong>Entreprise :</strong> {esc["company"]}</p>
  <p><strong>Salarié :</strong> {esc["employee"]}</p>
  <p><strong>Période :</strong> {esc["d0"]} au {esc["d1"]}</p>
  <p><strong>Durée :</strong> {len(days)} jour(s)</p>
  <p><strong>Statut :</strong> {esc["stage"]}</p>
  <p><strong>Commentaire :</strong><br>{esc["comment"]}</p>
  <p><a href="{esc["url"]}">Ouvrir les demandes d'absence dans EYWAI</a></p>
</body>
</html>
""".strip()

    sender = get_smtp_mail_sender()
    ok, err = sender.send_email_with_attachments(
        recipients,
        subject,
        text,
        html_content,
        [],
        require_delivery=False,
    )
    if not ok:
        logger.info("[absence_email] Email non envoyé: %s", err)


def notify_leave_request_email(
    row: dict[str, Any],
    *,
    event: str,
) -> None:
    """Email RH best-effort pour nouvelle demande ou validation manager."""
    try:
        company_id = str(row.get("company_id") or "")
        if not company_id:
            return
        settings = leave_notification_settings.get_settings(company_id)
        if not settings.enabled:
            return
        if event == "employee_request" and not settings.notify_on_employee_request:
            return
        if event == "manager_approval" and not settings.notify_after_manager_approval:
            return
        recipients = _resolve_leave_email_recipients(company_id)
        stage_label = (
            "en attente de validation manager"
            if event == "employee_request"
            and row.get("workflow_step") == "pending_manager"
            else "en attente de validation RH"
        )
        _send_leave_request_email(row, recipients=recipients, stage_label=stage_label)
    except Exception as exc:
        logger.info("[absence_email] Notification email ignorée: %s", exc)


def notify_absence_submitted(
    employee_id: str,
    company_id: str,
    absence_type: str,
    date_debut: str,
    date_fin: str,
) -> None:
    """Confirmation au salarié que sa demande est enregistrée."""
    label = ABSENCE_TYPE_LABELS.get(absence_type, "absence")
    message = (
        f"Votre demande de {label} du {date_debut} "
        f"au {date_fin} a bien été enregistrée "
        f"et est en attente de validation."
    )
    _insert_notification(employee_id, company_id, "absence_soumise", message)


def notify_absence_approved(
    employee_id: str,
    company_id: str,
    absence_type: str,
    date_debut: str,
    date_fin: str,
) -> None:
    """Notification au salarié : demande validée."""
    label = ABSENCE_TYPE_LABELS.get(absence_type, "absence")
    message = f"Votre demande de {label} du {date_debut} au {date_fin} a été approuvée."
    _insert_notification(employee_id, company_id, "absence_approuvee", message)


def notify_absence_rejected(
    employee_id: str,
    company_id: str,
    absence_type: str,
    date_debut: str,
    date_fin: str,
    reason: str | None = None,
) -> None:
    """Notification au salarié : demande refusée."""
    label = ABSENCE_TYPE_LABELS.get(absence_type, "absence")
    reason_text = f" Motif : {reason}." if reason else ""
    message = (
        f"Votre demande de {label} du {date_debut} "
        f"au {date_fin} a été refusée.{reason_text}"
    )
    _insert_notification(employee_id, company_id, "absence_refusee", message)


def notify_manager_new_request(
    manager_employee_id: str,
    company_id: str,
    employee_name: str,
    absence_type: str,
    date_debut: str,
    date_fin: str,
) -> None:
    """Notification au manager : nouvelle demande à valider."""
    label = ABSENCE_TYPE_LABELS.get(absence_type, "absence")
    message = (
        f"{employee_name} a soumis une demande de {label} "
        f"du {date_debut} au {date_fin} — en attente de "
        f"votre validation."
    )
    _insert_notification(manager_employee_id, company_id, "absence_a_valider", message)
