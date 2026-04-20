"""Orchestration widget Signatures en attente."""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.modules.signatures.infrastructure import queries as infra_queries
from app.modules.signatures.schemas.responses import PendingSignatureItem, PendingSignaturesResponse

logger = logging.getLogger(__name__)


def _iso(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc).isoformat()
        return value.isoformat()
    return str(value)


def _parse_date(value: Any) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    s = str(value).strip()
    if not s:
        return None
    try:
        if "T" in s:
            return datetime.fromisoformat(s.replace("Z", "+00:00")).date()
        return date.fromisoformat(s[:10])
    except Exception:
        return None


def _employee_block(row: Dict[str, Any]) -> Dict[str, Any]:
    emp = row.get("employees")
    if isinstance(emp, list) and emp:
        emp = emp[0]
    if isinstance(emp, dict):
        return emp
    return {}


def _days_until_expiry(expires_at: Any) -> Tuple[Optional[int], bool]:
    exp = _parse_date(expires_at)
    if exp is None:
        return None, False
    delta = (exp - date.today()).days
    is_urgent = delta < 3
    return delta, is_urgent


def _days_since_reminder(last_reminder_at: Any) -> Optional[int]:
    dt = _parse_date(last_reminder_at)
    if dt is None:
        return None
    return (date.today() - dt).days


def _document_name(row: Dict[str, Any], emp: Dict[str, Any]) -> str:
    title = (row.get("title") or "").strip()
    if title:
        return title
    fn = (emp.get("first_name") or "").strip()
    ln = (emp.get("last_name") or "").strip()
    name = f"{fn} {ln}".strip()
    if name:
        return f"Entretien {name}"
    year = row.get("year")
    if year is not None:
        return f"Entretien annuel {year}"
    return "Entretien"


def _row_to_item(row: Dict[str, Any]) -> PendingSignatureItem:
    emp = _employee_block(row)
    days_until, urgent_from_expiry = _days_until_expiry(row.get("expires_at"))
    is_urgent = urgent_from_expiry
    last_rem = row.get("last_reminder_at")
    days_since = _days_since_reminder(last_rem)

    return PendingSignatureItem(
        id=str(row["id"]),
        document_name=_document_name(row, emp),
        employee_id=str(row.get("employee_id") or ""),
        employee_first_name=emp.get("first_name"),
        employee_last_name=emp.get("last_name"),
        yousign_procedure_id=row.get("yousign_procedure_id"),
        signature_status=str(row.get("signature_status") or "pending"),
        sent_at=_iso(row.get("updated_at")),
        expires_at=_iso(row.get("expires_at")),
        days_until_expiry=days_until,
        is_urgent=is_urgent,
        last_reminder_at=_iso(last_rem),
        days_since_reminder=days_since,
        created_at=_iso(row.get("created_at")) or "",
    )


def _sort_key(item: PendingSignatureItem) -> Tuple[int, int, str]:
    """Priorité : urgent ; relance stale (>7j ou jamais) ; created_at ancien d'abord."""
    stale = (item.days_since_reminder is None) or (item.days_since_reminder > 7)
    return (
        0 if item.is_urgent else 1,
        0 if stale else 1,
        item.created_at or "",
    )


def get_widget_pending_rh(company_id: str) -> PendingSignaturesResponse:
    cfg = infra_queries.get_yousign_config(company_id)
    if cfg is None:
        return PendingSignaturesResponse(
            yousign_configured=False, total=0, items=[]
        )

    rows = infra_queries.get_pending_signatures_rh(company_id)
    items = [_row_to_item(r) for r in rows]
    items_sorted = sorted(items, key=_sort_key)
    top = items_sorted[:5]
    return PendingSignaturesResponse(
        yousign_configured=True,
        total=len(items),
        items=top,
    )


def get_widget_pending_employee(
    employee_id: str, company_id: str
) -> PendingSignaturesResponse:
    rows = infra_queries.get_pending_signatures_employee(employee_id, company_id)
    items = [_row_to_item(r) for r in rows]
    items_sorted = sorted(items, key=_sort_key)
    top = items_sorted[:5]
    return PendingSignaturesResponse(
        yousign_configured=None,
        total=len(items),
        items=top,
    )


def send_signature_reminder(review_id: str, company_id: str) -> Dict[str, Any]:
    """
    Relance Yousign pour un annual_review en pending (RH).
    Ne lève pas d'exception si l'API Yousign n'expose pas send_reminder.
    """
    from app.services.yousign_service import yousign_service

    row = infra_queries.get_annual_review_by_id(review_id)
    if not row:
        raise LookupError("Entretien non trouvé.")
    if str(row.get("company_id")) != str(company_id):
        raise PermissionError("Accès non autorisé à cet entretien.")
    if str(row.get("signature_status") or "") != "pending":
        raise ValueError("La procédure de signature n'est pas en attente.")
    proc = row.get("yousign_procedure_id")
    if not proc:
        raise ValueError("Aucune procédure Yousign associée.")

    fn = getattr(yousign_service, "send_reminder", None)
    if not callable(fn):
        logger.warning("YousignService.send_reminder : méthode absente.")
        return {"success": False, "error": "Méthode non disponible"}

    try:
        fn(str(proc))
    except Exception as e:
        logger.warning("Relance Yousign échouée: %s", e)
        return {"success": False, "error": str(e)}

    reminded = datetime.now(timezone.utc).isoformat()
    infra_queries.update_review_reminder_timestamp(review_id, reminded)
    return {"success": True, "reminded_at": reminded}
