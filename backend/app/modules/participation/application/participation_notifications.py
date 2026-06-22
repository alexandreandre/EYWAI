"""Notifications campagne bulletin d'option participation."""

from __future__ import annotations

import logging

from app.core.database import supabase
from app.modules.notifications.application.employee_document_alerts import (
    notify_employee_new_document,
)

logger = logging.getLogger(__name__)

NOTIF_BULLETIN_TO_RESPOND = "bulletin_participation_a_repondre"
NOTIF_BULLETIN_REMINDER = "bulletin_participation_rappel"
NOTIF_BULLETIN_RH_LATE = "bulletin_participation_retard_rh"
NOTIF_BULLETIN_DEFAULT_PEE = "bulletin_participation_defaut_pee"


def _insert_notification(
    employee_id: str,
    company_id: str,
    message: str,
    notification_type: str,
) -> None:
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
    except Exception as exc:
        logger.info("[participation_notif] insert failed %s: %s", employee_id, exc)


def notify_bulletin_to_respond(
    employee_id: str,
    company_id: str,
    *,
    dispositif_label: str,
    year: int,
    deadline_str: str,
) -> None:
    message = (
        f"Votre bulletin d'option {dispositif_label} {year} est disponible. "
        f"Merci de répondre avant le {deadline_str}."
    )
    _insert_notification(
        employee_id, company_id, message, NOTIF_BULLETIN_TO_RESPOND
    )
    notify_employee_new_document(
        employee_id,
        company_id,
        f"Bulletin d'option {dispositif_label} {year}",
        page_path="employee/participation",
        notification_type=NOTIF_BULLETIN_TO_RESPOND,
    )


def notify_bulletin_reminder(
    employee_id: str,
    company_id: str,
    *,
    dispositif_label: str,
    year: int,
    days_left: int,
) -> None:
    message = (
        f"Rappel : votre bulletin d'option {dispositif_label} {year} "
        f"attend une réponse (échéance dans {days_left} jour(s))."
    )
    _insert_notification(employee_id, company_id, message, NOTIF_BULLETIN_REMINDER)


def notify_rh_late_bulletins(
    rh_employee_id: str,
    company_id: str,
    *,
    count: int,
    year: int,
) -> None:
    if count <= 0:
        return
    message = (
        f"{count} bulletin(s) d'option participation {year} "
        f"sans réponse — relance recommandée."
    )
    _insert_notification(
        rh_employee_id, company_id, message, NOTIF_BULLETIN_RH_LATE
    )


def notify_rh_default_pee_applied(
    rh_employee_id: str,
    company_id: str,
    *,
    count: int,
    year: int,
) -> None:
    if count <= 0:
        return
    message = (
        f"{count} salarié(s) passés en placement PEE par défaut "
        f"(participation {year}, délai 15 jours dépassé)."
    )
    _insert_notification(
        rh_employee_id, company_id, message, NOTIF_BULLETIN_DEFAULT_PEE
    )
