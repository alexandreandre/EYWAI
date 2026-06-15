"""Service applicatif import DSN."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from app.modules.dsn_import.application.commit import commit_batch
from app.modules.dsn_import.application.cumuls import plan_cumul_items
from app.modules.dsn_import.application.mapping import build_preview_items
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
    return {
        "batch": batch,
        "items": items,
        "preview": batch.get("preview") or {},
        "summary": batch.get("summary") or {},
    }


def list_batches(limit: int = 50) -> List[Dict[str, Any]]:
    return repo.list_batches(limit=limit)


def execute_commit(
    batch_id: str,
    overrides: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    return commit_batch(batch_id, overrides=overrides)


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
