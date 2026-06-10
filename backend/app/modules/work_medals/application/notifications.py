"""Notifications in-app pour les médailles du travail."""

from __future__ import annotations

import logging

from app.core.database import supabase
from app.modules.work_medals.domain.rules import MEDAL_LEVEL_LABELS

logger = logging.getLogger(__name__)


def _insert_notification(
    employee_id: str,
    company_id: str,
    notif_type: str,
    message: str,
) -> bool:
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
        return True
    except Exception as exc:
        logger.info("[work_medal_notif] Non insérée: %s", exc)
        return False


def notify_employee_approved(
    employee_id: str,
    company_id: str,
    medal_level: str,
    amount: float,
    payroll_month: int,
    payroll_year: int,
) -> bool:
    label = MEDAL_LEVEL_LABELS.get(medal_level, medal_level)  # type: ignore[arg-type]
    message = (
        f"Votre prime {label} de {amount:.2f} € a été validée "
        f"pour le bulletin de {payroll_month:02d}/{payroll_year}."
    )
    return _insert_notification(employee_id, company_id, "medaille_travail", message)
