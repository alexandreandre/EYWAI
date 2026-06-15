"""Service applicatif import DSN."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from app.modules.dsn_import.application.commit import commit_batch
from app.modules.dsn_import.application.cumuls import build_cumuls_summary, plan_cumul_items
from app.modules.dsn_import.application.mapping import (
    apply_legal_name_to_preview,
    build_preview_items,
    enrich_summary_from_items,
)
from app.modules.dsn_import.domain.parser import parse_dsn_files
from app.modules.dsn_import.domain.validation import validate_parsed_dsn
from app.modules.dsn_import.infrastructure import repository as repo


def parse_and_stage(
    files: List[Tuple[str, bytes]],
    uploaded_by: str,
) -> Dict[str, Any]:
    """Parse les fichiers, construit preview, persiste batch + items."""
    parsed = parse_dsn_files(files)
    anomalies = validate_parsed_dsn(parsed)
    preview_items, summary = build_preview_items(parsed)
    cumul_items = plan_cumul_items(parsed)
    all_items = preview_items + cumul_items

    # Détection create vs update (best effort sans bloquer)
    _enrich_actions(all_items)

    summary = enrich_summary_from_items(summary, parsed, all_items)

    periods = sorted(
        {
            str(it.get("mapped_payload", {}).get("period"))
            for it in cumul_items
            if it.get("mapped_payload", {}).get("period")
        }
    )
    summary["cumul_month_count"] = len(periods)
    summary["cumul_periods"] = periods
    summary["cumuls_summary"] = build_cumuls_summary(cumul_items)

    suggested_name = None
    etab_count = summary.get("establishment_count") or 0
    if siren := parsed.siren:
        from app.modules.dsn_import.application.siren_lookup import lookup_company_name_by_siren

        suggested_name = lookup_company_name_by_siren(siren)
        if suggested_name:
            summary["suggested_company_name"] = suggested_name
            apply_legal_name_to_preview(
                all_items,
                suggested_name,
                single_establishment=etab_count == 1,
            )

    file_names = [name for name, _ in files]
    batch_id = repo.insert_batch(
        {
            "uploaded_by": uploaded_by,
            "file_names": file_names,
            "siren": parsed.siren,
            "period_min": parsed.period_min,
            "period_max": parsed.period_max,
            "status": "previewed",
            "summary": summary,
            "preview": {
                "anomalies": anomalies,
                "can_commit": not any(a.get("severity") == "blocking" for a in anomalies),
                # Snapshot enrichi pour restaurer l'écran preview après un rechargement.
                "items": all_items,
            },
        }
    )
    if not batch_id:
        raise RuntimeError("Impossible de créer le batch d'import")

    db_items = [
        {
            "batch_id": batch_id,
            "item_type": it["item_type"],
            "source_ref": it["source_ref"],
            "action": it.get("action", "create"),
            "mapped_payload": it.get("mapped_payload", {}),
            "anomalies": it.get("anomalies", []),
            "status": "pending",
        }
        for it in all_items
    ]
    repo.insert_items(db_items)

    return {
        "batch_id": batch_id,
        "summary": summary,
        "anomalies": anomalies,
        "items": all_items,
        "can_commit": not any(a.get("severity") == "blocking" for a in anomalies),
    }


def _enrich_actions(items: List[Dict[str, Any]]) -> None:
    for it in items:
        payload = it.get("mapped_payload") or {}
        item_type = it.get("item_type")
        if item_type == "group":
            siren = payload.get("siren")
            if siren and repo.find_group_by_siren(siren):
                it["action"] = "update"
        elif item_type == "establishment":
            siret = payload.get("siret")
            if siret and repo.find_company_by_siret(siret):
                it["action"] = "update"
        elif item_type == "employee":
            siret = (it.get("source_ref") or "").split(":")[1] if ":" in (it.get("source_ref") or "") else ""
            nir = payload.get("nir")
            co = repo.find_company_by_siret(siret) if siret else None
            if co and nir and repo.find_employee_by_nir(str(co["id"]), nir):
                it["action"] = "update"


def get_batch_detail(batch_id: str) -> Optional[Dict[str, Any]]:
    batch = repo.get_batch(batch_id)
    if not batch:
        return None
    items = repo.list_items(batch_id)
    summary = batch.get("summary") or {}
    return {
        "batch": batch,
        "items": items,
        "preview": batch.get("preview") or {},
        "summary": summary,
    }


def revalidate_preview(
    batch_id: str,
    payload_edits: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Recalcule anomalies et can_commit après éditions preview."""
    from app.modules.dsn_import.application.revalidate import revalidate_batch_preview

    batch = repo.get_batch(batch_id)
    if not batch:
        raise LookupError("Batch introuvable")
    items = repo.list_items(batch_id)
    # Reconstruire items preview avec champs UI
    preview_items = []
    for row in items:
        preview_items.append(
            {
                "item_type": row.get("item_type"),
                "source_ref": row.get("source_ref"),
                "action": row.get("action", "create"),
                "mapped_payload": row.get("mapped_payload") or {},
                "label": (row.get("mapped_payload") or {}).get("group_name")
                or (row.get("mapped_payload") or {}).get("company_name")
                or row.get("source_ref"),
            }
        )
    result = revalidate_batch_preview(batch, preview_items, payload_edits)
    return result


def list_batches(limit: int = 50) -> List[Dict[str, Any]]:
    return repo.list_batches(limit=limit)


def execute_commit(
    batch_id: str,
    overrides: Optional[Dict[str, str]] = None,
    payload_edits: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    return commit_batch(batch_id, overrides=overrides, payload_edits=payload_edits)


def begin_commit(
    batch_id: str,
    overrides: Optional[Dict[str, str]] = None,
    payload_edits: Optional[Dict[str, Dict[str, Any]]] = None,
) -> bool:
    """
    Bascule le batch en 'committing' avant lancement en arrière-plan.
    Retourne True si le commit doit être lancé, False s'il tourne déjà.
    """
    batch = repo.get_batch(batch_id)
    if not batch:
        raise LookupError("Batch introuvable")
    status = batch.get("status")
    if status == "committed":
        raise ValueError("Ce batch a déjà été validé")
    if status == "committing":
        return False
    repo.update_batch(
        batch_id,
        {
            "status": "committing",
            "summary": {
                **(batch.get("summary") or {}),
                "commit_request": {
                    "overrides": overrides or {},
                    "payload_edits": payload_edits or {},
                },
            },
        },
    )
    return True


def run_commit(
    batch_id: str,
    overrides: Optional[Dict[str, str]] = None,
    payload_edits: Optional[Dict[str, Dict[str, Any]]] = None,
) -> None:
    """Exécute le commit (tâche d'arrière-plan). Trace l'échec dans le batch."""
    from app.core.logging import get_logger

    logger = get_logger("modules.dsn_import.run_commit")
    try:
        commit_batch(batch_id, overrides=overrides, payload_edits=payload_edits)
    except Exception as exc:
        logger.exception("Commit arrière-plan batch %s échoué", batch_id)
        batch = repo.get_batch(batch_id) or {}
        repo.update_batch(
            batch_id,
            {
                "status": "failed",
                "error_message": str(exc),
                "summary": {
                    **(batch.get("summary") or {}),
                    "commit_report": {
                        "stats": {"created": 0, "updated": 0, "skipped": 0, "failed": 0},
                        "errors": [str(exc)],
                        "group_id": None,
                        "companies": {},
                        "imported_employees": [],
                    },
                },
            },
        )


def activate_imported_employee(
    employee_id: str,
    company_id: str,
    email: str,
    granted_by_user_id: Optional[str] = None,
) -> Dict[str, Any]:
    from app.modules.employees.application.commands import activate_imported_employee_account

    return activate_imported_employee_account(
        employee_id=employee_id,
        company_id=company_id,
        email=email,
        granted_by_user_id=granted_by_user_id,
    )
