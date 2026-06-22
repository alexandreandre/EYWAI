"""Salariés créés par import DSN et absents du fichier en cours (réimport)."""

from __future__ import annotations

from typing import Any, Dict, List

from fastapi import HTTPException

from app.core.logging import get_logger
from app.modules.dsn_import.domain.user_messages import _mask_nir
from app.modules.dsn_import.infrastructure import repository as repo

logger = get_logger("modules.dsn_import.orphan_employees")

DSN_PLACEHOLDER_EMAIL_SUFFIX = ".dsn-import.local"


def _employee_display_name(row: Dict[str, Any]) -> str:
    return f"{row.get('first_name', '')} {row.get('last_name', '')}".strip() or "Salarié"


def _dsn_nirs_from_items(items: List[Dict[str, Any]]) -> set[str]:
    nirs: set[str] = set()
    for it in items:
        if it.get("item_type") != "employee":
            continue
        nir = ((it.get("mapped_payload") or {}).get("nir") or "").strip()
        if nir:
            nirs.add(nir)
    return nirs


def compute_reimport_orphans(
    items: List[Dict[str, Any]],
    company_id: str,
) -> Dict[str, Any]:
    """
    Salariés « fantômes » supprimables au réimport :
    - email placeholder DSN (*.dsn-import.local)
    - pas de compte utilisateur activé
    - NIR absent du fichier DSN analysé
    """
    if not company_id:
        return {"count": 0, "employees": []}

    dsn_nirs = _dsn_nirs_from_items(items)
    orphans: List[Dict[str, Any]] = []

    for emp in repo.list_dsn_placeholder_employees(company_id):
        if emp.get("user_id"):
            continue
        nir = (emp.get("nir") or "").strip()
        if nir and nir in dsn_nirs:
            continue
        orphans.append(
            {
                "employee_id": str(emp["id"]),
                "employee_name": _employee_display_name(emp),
                "nir_masked": _mask_nir(nir) if nir else "—",
            }
        )

    return {"count": len(orphans), "employees": orphans}


def attach_reimport_orphans(
    items: List[Dict[str, Any]],
    summary: Dict[str, Any],
    *,
    target_company_id: str | None,
    import_mode: str,
) -> None:
    """Attache le décompte des salariés supprimables au summary preview."""
    if (import_mode or "").strip().lower() != "monthly" or not target_company_id:
        summary.pop("reimport_orphans", None)
        return
    summary["reimport_orphans"] = compute_reimport_orphans(items, str(target_company_id))


def remove_reimport_orphans(
    items: List[Dict[str, Any]],
    company_id: str,
) -> Dict[str, Any]:
    """Supprime les salariés fantômes détectés pour l'entreprise."""
    from app.modules.employees.application.commands import delete_employee

    orphans = compute_reimport_orphans(items, company_id)
    removed: List[Dict[str, str]] = []
    failed: List[Dict[str, str]] = []

    for orphan in orphans.get("employees") or []:
        employee_id = str(orphan.get("employee_id") or "")
        if not employee_id:
            continue
        try:
            delete_employee(employee_id, company_id)
            removed.append(
                {
                    "employee_id": employee_id,
                    "employee_name": str(orphan.get("employee_name") or ""),
                }
            )
        except HTTPException as exc:
            logger.warning(
                "Suppression salarié fantôme %s échouée : %s",
                employee_id,
                exc.detail,
            )
            failed.append(
                {
                    "employee_id": employee_id,
                    "employee_name": str(orphan.get("employee_name") or ""),
                    "error": str(exc.detail),
                }
            )
        except Exception as exc:
            logger.exception("Suppression salarié fantôme %s échouée", employee_id)
            failed.append(
                {
                    "employee_id": employee_id,
                    "employee_name": str(orphan.get("employee_name") or ""),
                    "error": str(exc),
                }
            )

    return {
        "requested_count": orphans.get("count", 0),
        "removed_count": len(removed),
        "removed": removed,
        "failed": failed,
    }
