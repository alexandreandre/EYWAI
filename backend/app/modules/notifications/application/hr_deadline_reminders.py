"""Relances e-mail RH pour échéances CDD, période d'essai et titre de séjour."""

from __future__ import annotations

import html
import logging
from datetime import date
from typing import Any, Dict, List, Set

from app.core.database import supabase
from app.modules.employees.domain.deadline_reminders import (
    DeadlineCandidate,
    list_hr_deadline_candidates,
)
from app.modules.employees.domain.rules import is_dsn_import_placeholder_email
from app.modules.platform_settings.application.email_config import get_resolved_email_config
from app.modules.super_admin.infrastructure.providers import get_user_email
from app.modules.users.infrastructure.queries import (
    fetch_company_name,
    fetch_company_users_rows,
)
from app.shared.infrastructure.email.smtp_sender import get_smtp_mail_sender

logger = logging.getLogger(__name__)

_RH_ROLES = frozenset({"admin", "rh", "collaborateur_rh"})


def fetch_employees_for_hr_deadline_reminders(company_id: str) -> List[Dict[str, Any]]:
    resp = (
        supabase.table("employees")
        .select(
            "id, first_name, last_name, employment_status, contract_type, "
            "contract_end_date, hire_date, "
            "is_subject_to_residence_permit, residence_permit_expiry_date, "
            "trial_period:trial_periods(end_date, status)"
        )
        .eq("company_id", company_id)
        .execute()
    )
    rows = list(resp.data or [])
    # Une relation inverse remonte une liste : on ne garde que la période
    # active, celle sur laquelle porte la relance.
    for row in rows:
        trials = row.get("trial_period")
        if isinstance(trials, list):
            active = [t for t in trials if t.get("status") == "en_cours"]
            row["trial_period"] = active[0] if active else None
    return rows


def fetch_rh_recipient_emails(company_id: str) -> List[str]:
    rows = fetch_company_users_rows(company_id)
    emails: Set[str] = set()
    unreachable: Set[str] = set()
    for row in rows:
        role = str(row.get("role") or "").strip().lower()
        if role not in _RH_ROLES:
            continue
        # Un accès révoqué ne doit plus être relancé. Le filtre est ici et non dans
        # fetch_company_users_rows, qui sert aussi l'écran d'administration : celui-ci
        # doit continuer à montrer les accès révoqués pour pouvoir les rétablir.
        if row.get("is_active") is False:
            continue
        user_id = str(row.get("user_id") or "").strip()
        if not user_id:
            continue
        email = get_user_email(user_id)
        if not email or "@" not in email:
            continue
        email = email.strip().lower()
        # Une adresse fabriquée identifie un compte, elle ne joint personne. L'envoi
        # échouerait sans conséquence visible (require_delivery=False) et l'on croirait
        # avoir prévenu un RH qui n'a jamais rien reçu.
        if is_dsn_import_placeholder_email(email):
            unreachable.add(email)
            continue
        emails.add(email)

    if unreachable:
        logger.warning(
            "[hr_deadline_reminder] company=%s : %d destinataire(s) RH sans adresse "
            "réelle, aucune relance ne leur parviendra (%s)",
            company_id,
            len(unreachable),
            ", ".join(sorted(unreachable)),
        )
    return sorted(emails)


def was_reminder_sent(
    company_id: str,
    employee_id: str,
    reminder_type: str,
    deadline_date: date,
) -> bool:
    try:
        resp = (
            supabase.table("hr_deadline_reminder_logs")
            .select("id")
            .eq("company_id", company_id)
            .eq("employee_id", employee_id)
            .eq("reminder_type", reminder_type)
            .eq("deadline_date", deadline_date.isoformat())
            .limit(1)
            .execute()
        )
        return bool(resp.data)
    except Exception as exc:
        logger.warning(
            "[hr_deadline_reminder] Lookup log impossible company=%s employee=%s: %s",
            company_id,
            employee_id,
            exc,
        )
        return False


def log_reminder_sent(
    company_id: str,
    employee_id: str,
    reminder_type: str,
    deadline_date: date,
) -> bool:
    try:
        supabase.table("hr_deadline_reminder_logs").insert(
            {
                "company_id": company_id,
                "employee_id": employee_id,
                "reminder_type": reminder_type,
                "deadline_date": deadline_date.isoformat(),
            }
        ).execute()
        return True
    except Exception as exc:
        logger.warning(
            "[hr_deadline_reminder] Insert log impossible company=%s employee=%s: %s",
            company_id,
            employee_id,
            exc,
        )
        return False


def _build_email_subject(company_name: str, count: int) -> str:
    suffix = "s" if count > 1 else ""
    name = company_name or "votre entreprise"
    return f"[EYWAI] {count} échéance{suffix} RH à traiter — {name}"


def _format_candidate_line(candidate: DeadlineCandidate) -> str:
    name = f"{candidate.first_name} {candidate.last_name}".strip() or "Salarié"
    days = candidate.days_remaining
    if days == 0:
        delay = "aujourd'hui"
    elif days == 1:
        delay = "demain"
    else:
        delay = f"dans {days} jours"
    return f"- {name} : {candidate.label} ({delay})"


def _build_email_content(
    company_name: str,
    candidates: List[DeadlineCandidate],
) -> tuple[str, str]:
    config = get_resolved_email_config()
    dashboard_url = f"{config.frontend_url.rstrip('/')}/dashboard"
    company_label = company_name or "votre entreprise"
    lines = [_format_candidate_line(c) for c in candidates]
    body_lines = "\n".join(lines)

    text_content = f"""Bonjour,

Des échéances RH nécessitent votre attention pour {company_label} :

{body_lines}

Consultez le cockpit RH :
{dashboard_url}

Cordialement,
L'équipe EYWAI
"""

    html_items = "".join(
        f"<li>{html.escape(line.lstrip('- '))}</li>" for line in lines
    )
    html_content = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
  <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
    <div style="background-color: #2563eb; color: white; padding: 20px; text-align: center; border-radius: 5px 5px 0 0;">
      <h1 style="margin: 0; font-size: 20px;">Échéances RH à traiter</h1>
    </div>
    <div style="background-color: #f9fafb; padding: 30px; border: 1px solid #e5e7eb;">
      <p>Bonjour,</p>
      <p>Des échéances RH nécessitent votre attention pour <strong>{html.escape(company_label)}</strong>&nbsp;:</p>
      <ul>{html_items}</ul>
      <p style="text-align: center; margin: 24px 0;">
        <a href="{html.escape(dashboard_url)}"
           style="display: inline-block; padding: 12px 24px; background-color: #2563eb; color: white; text-decoration: none; border-radius: 5px;">
          Ouvrir le cockpit RH
        </a>
      </p>
    </div>
    <p style="text-align: center; color: #6b7280; font-size: 12px;">Cet e-mail a été envoyé par EYWAI</p>
  </div>
</body>
</html>"""
    return text_content.strip(), html_content


def _send_grouped_email(
    recipients: List[str],
    company_name: str,
    candidates: List[DeadlineCandidate],
) -> tuple[int, int]:
    if not recipients or not candidates:
        return 0, 0

    sender = get_smtp_mail_sender()
    subject = _build_email_subject(company_name, len(candidates))
    text_content, html_content = _build_email_content(company_name, candidates)

    sent = 0
    errors = 0
    for to_email in recipients:
        ok, err = sender.send_multipart_email(
            to_email=to_email,
            subject=subject,
            text_content=text_content,
            html_content=html_content,
            require_delivery=False,
        )
        if ok:
            sent += 1
        else:
            errors += 1
            logger.warning(
                "[hr_deadline_reminder] E-mail non envoyé à %s: %s",
                to_email,
                err,
            )
    return sent, errors


def send_hr_deadline_reminders(company_id: str) -> dict:
    """
    Envoie des relances e-mail RH pour les échéances dans les fenêtres J-15 / J-30.
    Chaque combinaison (salarié, type, date) n'est notifiée qu'une seule fois.
    """
    try:
        employees = fetch_employees_for_hr_deadline_reminders(company_id)
        all_candidates = list_hr_deadline_candidates(employees)

        to_send: List[DeadlineCandidate] = []
        skipped = 0
        for candidate in all_candidates:
            if was_reminder_sent(
                company_id,
                candidate.employee_id,
                candidate.reminder_type,
                candidate.deadline,
            ):
                skipped += 1
                continue
            to_send.append(candidate)

        if not to_send:
            return {"sent": 0, "skipped": skipped, "errors": 0, "emails_sent": 0}

        recipients = fetch_rh_recipient_emails(company_id)
        company_name = fetch_company_name(company_id) or ""
        emails_sent, email_errors = _send_grouped_email(
            recipients,
            company_name,
            to_send,
        )

        if emails_sent == 0 and recipients:
            return {
                "sent": 0,
                "skipped": skipped,
                "errors": max(1, email_errors),
                "emails_sent": 0,
            }

        logged = 0
        log_errors = 0
        for candidate in to_send:
            if log_reminder_sent(
                company_id,
                candidate.employee_id,
                candidate.reminder_type,
                candidate.deadline,
            ):
                logged += 1
            else:
                log_errors += 1

        return {
            "sent": logged,
            "skipped": skipped,
            "errors": email_errors + log_errors,
            "emails_sent": emails_sent,
        }
    except Exception as exc:
        logger.error("[hr_deadline_reminder] Erreur company=%s: %s", company_id, exc)
        return {"sent": 0, "skipped": 0, "errors": 1, "emails_sent": 0}
