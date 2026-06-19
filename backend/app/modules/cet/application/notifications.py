"""Notifications in-app (best effort) pour le module CET."""

from __future__ import annotations

import logging

from app.core.database import supabase

logger = logging.getLogger(__name__)

MOVEMENT_LABELS = {
    "deposit_hs": "épargne d'heures sup",
    "deposit_cp": "transfert de congés payés",
    "withdraw_rest": "pose de congé CET",
    "adjustment": "ajustement CET",
}


def _insert_notification(
    employee_id: str,
    company_id: str,
    notif_type: str,
    message: str,
) -> None:
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
        logger.info("[cet_notif] Non insérée: %s", e)


def _employee_display_name(employee_id: str) -> str:
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


def _movement_summary(movement_type: str, hours: float, days: float) -> str:
    label = MOVEMENT_LABELS.get(movement_type, "demande CET")
    if movement_type == "deposit_cp":
        return f"{label} ({days:g} j)"
    if hours:
        return f"{label} ({hours:g} h)"
    return label


def notify_cet_submitted(
    employee_id: str,
    company_id: str,
    movement_type: str,
    *,
    hours: float = 0,
    days: float = 0,
) -> None:
    summary = _movement_summary(movement_type, hours, days)
    _insert_notification(
        employee_id,
        company_id,
        "cet_demande_soumise",
        f"Votre demande CET ({summary}) a été enregistrée.",
    )


def notify_manager_new_cet_request(
    manager_employee_id: str,
    company_id: str,
    requester_employee_id: str,
    movement_type: str,
    *,
    hours: float = 0,
    days: float = 0,
) -> None:
    name = _employee_display_name(requester_employee_id)
    summary = _movement_summary(movement_type, hours, days)
    _insert_notification(
        manager_employee_id,
        company_id,
        "cet_a_valider",
        f"{name} — demande CET à valider : {summary}.",
    )


def notify_cet_manager_decision(
    employee_id: str,
    company_id: str,
    *,
    approved: bool,
    movement_type: str,
    hours: float = 0,
    days: float = 0,
    reason: str | None = None,
) -> None:
    summary = _movement_summary(movement_type, hours, days)
    if approved:
        msg = f"Votre demande CET ({summary}) a été approuvée par votre manager."
        notif_type = "cet_approuve_manager"
    else:
        suffix = f" Motif : {reason}" if reason else ""
        msg = f"Votre demande CET ({summary}) a été refusée par votre manager.{suffix}"
        notif_type = "cet_refuse_manager"
    _insert_notification(employee_id, company_id, notif_type, msg)


def notify_cet_rh_decision(
    employee_id: str,
    company_id: str,
    *,
    approved: bool,
    movement_type: str,
    hours: float = 0,
    days: float = 0,
    reason: str | None = None,
) -> None:
    summary = _movement_summary(movement_type, hours, days)
    if approved:
        msg = f"Votre demande CET ({summary}) a été validée."
        notif_type = "cet_approuve"
    else:
        suffix = f" Motif : {reason}" if reason else ""
        msg = f"Votre demande CET ({summary}) a été refusée.{suffix}"
        notif_type = "cet_refuse"
    _insert_notification(employee_id, company_id, notif_type, msg)


def notify_cet_pending_rh_after_manager(
    manager_employee_id: str,
    company_id: str,
    requester_employee_id: str,
) -> None:
    name = _employee_display_name(requester_employee_id)
    _insert_notification(
        manager_employee_id,
        company_id,
        "cet_approuve_manager",
        f"Demande CET de {name} transmise à la validation RH.",
    )
