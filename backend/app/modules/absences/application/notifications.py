"""Notifications in-app (best effort) pour le module absences."""

from __future__ import annotations

import logging
from typing import Any, List

from app.core.database import supabase

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
    message = (
        f"Votre demande de {label} du {date_debut} "
        f"au {date_fin} a été approuvée."
    )
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
    _insert_notification(
        manager_employee_id, company_id, "absence_a_valider", message
    )
