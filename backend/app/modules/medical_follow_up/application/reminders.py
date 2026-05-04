# app/modules/medical_follow_up/application/reminders.py
"""Rappels in-app pour le suivi médical (notifications salarié)."""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any, Dict, List

from app.core.database import supabase

logger = logging.getLogger(__name__)

VISIT_TYPE_LABELS: Dict[str, str] = {
    "visite_embauche": "Visite d'embauche",
    "visite_periodique": "Visite périodique",
    "visite_reprise": "Visite de reprise",
    "visite_pre_reprise": "Visite de pré-reprise",
    "aptitude_sir_avant_affectation": "Aptitude SIR avant affectation",
    "visite_mi_carriere": "Visite mi-carrière",
    "vip_avant_affectation_mineur_nuit": "VIP avant affectation (mineur/nuit)",
    "reprise": "Visite de reprise",
    "vip": "Visite VIP",
    "sir": "Visite SIR",
    "mi_carriere_45": "Visite mi-carrière (45 ans)",
    "demande": "Visite à la demande",
}

_ACTIVE_STATUSES = ("a_faire", "planifiee")


def _visit_label(visit_type: str) -> str:
    return VISIT_TYPE_LABELS.get(visit_type, visit_type.replace("_", " "))


def _parse_due(due_raw: Any) -> date | None:
    if due_raw is None:
        return None
    if isinstance(due_raw, date):
        return due_raw
    if isinstance(due_raw, str):
        try:
            return date.fromisoformat(due_raw[:10])
        except (ValueError, TypeError):
            return None
    return None


def _rows_same_shape_as_list_obligations(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Normalise le join employee → clé `employee` pour ObligationListDTO.from_row."""
    out: List[Dict[str, Any]] = []
    for r in rows:
        row = dict(r)
        emp = row.get("employee")
        if isinstance(emp, list) and emp:
            row["employee"] = emp[0]
        out.append(row)
    return out


def list_overdue_obligation_rows(company_id: str) -> List[Dict[str, Any]]:
    """Obligations en retard (due_date < aujourd'hui, statut actif)."""
    today_s = date.today().isoformat()
    res = (
        supabase.table("medical_follow_up_obligations")
        .select("*, employee:employees(first_name, last_name)")
        .eq("company_id", company_id)
        .in_("status", list(_ACTIVE_STATUSES))
        .lt("due_date", today_s)
        .order("due_date")
        .execute()
    )
    return _rows_same_shape_as_list_obligations(list(res.data or []))


def list_upcoming_obligation_rows(company_id: str, days: int = 30) -> List[Dict[str, Any]]:
    """Obligations à échéance dans les ``days`` prochains jours (inclus aujourd'hui), non complétées."""
    today = date.today()
    end = today + timedelta(days=max(0, days))
    res = (
        supabase.table("medical_follow_up_obligations")
        .select("*, employee:employees(first_name, last_name)")
        .eq("company_id", company_id)
        .in_("status", list(_ACTIVE_STATUSES))
        .gte("due_date", today.isoformat())
        .lte("due_date", end.isoformat())
        .order("due_date")
        .execute()
    )
    return _rows_same_shape_as_list_obligations(list(res.data or []))


def _reminder_message(visit_type: str, due: date, today: date) -> str:
    label = _visit_label(visit_type)
    days_left = (due - today).days
    if days_left < 0:
        late = -days_left
        return (
            f"{label} : échéance dépassée de {late} jour(s). "
            "Merci de planifier ou de réaliser votre visite médicale."
        )
    if days_left == 0:
        return f"{label} : échéance aujourd'hui. Pensez à votre visite médicale."
    if days_left <= 7:
        return f"{label} : échéance dans {days_left} jour(s). À traiter en priorité."
    return f"{label} : échéance dans {days_left} jour(s) (moins d'un mois)."


def send_medical_reminders(company_id: str) -> dict:
    """
    Envoie des rappels pour les obligations dont l'échéance est dans les 30 prochains jours
    ou déjà dépassée (statuts a_faire / planifiee uniquement).
    """
    try:
        today = date.today()
        horizon = today + timedelta(days=30)
        res = (
            supabase.table("medical_follow_up_obligations")
            .select("id, employee_id, company_id, visit_type, due_date, status")
            .eq("company_id", company_id)
            .in_("status", list(_ACTIVE_STATUSES))
            .lte("due_date", horizon.isoformat())
            .execute()
        )
        rows = list(res.data or [])

        sent = 0
        errors = 0
        for row in rows:
            due = _parse_due(row.get("due_date"))
            if due is None:
                errors += 1
                continue
            employee_id = row.get("employee_id")
            visit_type = str(row.get("visit_type") or "")
            if not employee_id:
                errors += 1
                continue
            message = _reminder_message(visit_type, due, today)
            try:
                supabase.table("notifications").insert(
                    {
                        "employee_id": str(employee_id),
                        "company_id": company_id,
                        "type": "rappel_medical",
                        "message": message,
                        "is_read": False,
                    }
                ).execute()
                sent += 1
            except Exception as ex:  # noqa: BLE001
                logger.warning(
                    "[reminders] Insert notification impossible obligation=%s employee=%s: %s",
                    row.get("id"),
                    employee_id,
                    ex,
                )
                errors += 1

        return {"sent": sent, "errors": errors}
    except Exception as e:  # noqa: BLE001
        logger.error("[reminders] Erreur: %s", e)
        return {"sent": 0, "errors": 1}
