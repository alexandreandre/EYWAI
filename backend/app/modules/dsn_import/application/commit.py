"""Commit idempotent d'un batch d'import DSN."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.core.database import get_supabase_admin_client
from app.core.logging import get_logger
from app.modules.company_groups.infrastructure.repository import CompanyGroupRepository
from app.modules.dsn_import.application.cumuls import write_cumuls_file
from app.modules.dsn_import.infrastructure import repository as repo
from app.modules.employees.application.commands import create_employee_imported, update_employee
from app.modules.employees.infrastructure.repository import EmployeeRepository

logger = get_logger("modules.dsn_import.commit")

_group_repo = CompanyGroupRepository()
_employee_repo = EmployeeRepository()


def commit_batch(
    batch_id: str,
    overrides: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """
    Exécute le commit d'un batch previewed.
    overrides : {source_ref: action} où action in create|update|skip
    """
    batch = repo.get_batch(batch_id)
    if not batch:
        raise LookupError("Batch introuvable")
    if batch.get("status") == "committed":
        raise ValueError("Ce batch a déjà été validé")

    items = repo.list_items(batch_id)
    overrides = overrides or {}

    # Index résolutions
    group_id: Optional[str] = None
    company_by_siret: Dict[str, str] = {}
    employee_by_ref: Dict[str, Dict[str, Any]] = {}
    stats = {"created": 0, "updated": 0, "skipped": 0, "failed": 0}
    errors: List[str] = []
    imported_employees: List[Dict[str, Any]] = []

    ordered_types = ["group", "establishment", "collective_agreement", "employee", "cumul"]
    items_sorted = sorted(
        items,
        key=lambda i: ordered_types.index(i.get("item_type", "employee"))
        if i.get("item_type") in ordered_types
        else 99,
    )

    for item in items_sorted:
        item_id = str(item["id"])
        source_ref = item.get("source_ref", "")
        action = overrides.get(source_ref, item.get("action", "create"))
        if action == "skip":
            repo.update_item(item_id, {"status": "skipped", "action": "skip"})
            stats["skipped"] += 1
            continue

        item_type = item.get("item_type")
        payload = item.get("mapped_payload") or {}

        try:
            target_id = None
            if item_type == "group":
                target_id, created = _commit_group(payload, action)
                stats["created" if created else "updated"] += 1
                group_id = target_id
            elif item_type == "establishment":
                target_id, created = _commit_establishment(payload, group_id, action)
                stats["created" if created else "updated"] += 1
                if payload.get("siret"):
                    company_by_siret[payload["siret"]] = target_id
            elif item_type == "collective_agreement":
                _commit_collective_agreement(payload, company_by_siret)
                stats["updated"] += 1
            elif item_type == "employee":
                target_id, created, emp_row = _commit_employee(
                    payload, source_ref, company_by_siret, action
                )
                stats["created" if created else "updated"] += 1
                employee_by_ref[source_ref] = emp_row or {}
                if target_id and emp_row and created and not emp_row.get("user_id"):
                    imported_employees.append(
                        {
                            "employee_id": target_id,
                            "company_id": str(emp_row.get("company_id", "")),
                            "full_name": (
                                f"{emp_row.get('first_name', '')} {emp_row.get('last_name', '')}"
                            ).strip(),
                            "placeholder_email": emp_row.get("email"),
                            "employment_status": emp_row.get("employment_status"),
                        }
                    )
            elif item_type == "cumul":
                _commit_cumul(payload, company_by_siret, employee_by_ref)
                stats["updated"] += 1

            repo.update_item(
                item_id,
                {
                    "status": "committed",
                    "action": action,
                    "target_id": target_id,
                },
            )
        except Exception as exc:
            logger.exception("Commit item %s échoué", source_ref)
            errors.append(f"{source_ref} : {exc}")
            repo.update_item(item_id, {"status": "failed"})
            stats["failed"] += 1

    status = "committed" if not errors else "failed"
    report = {
        "stats": stats,
        "errors": errors,
        "group_id": group_id,
        "companies": company_by_siret,
        "imported_employees": imported_employees,
    }
    repo.update_batch(
        batch_id,
        {"status": status, "summary": {**(batch.get("summary") or {}), "commit_report": report}},
    )
    return report


def _commit_group(payload: Dict[str, Any], action: str) -> tuple[str, bool]:
    siren = payload.get("siren", "")
    existing = repo.find_group_by_siren(siren)
    if existing and action in ("create", "update"):
        gid = str(existing["id"])
        if action == "update":
            _group_repo.update(gid, {
                k: payload[k]
                for k in ("group_name", "siren", "description")
                if k in payload and payload[k]
            })
        return gid, False
    if existing:
        return str(existing["id"]), False

    row = _group_repo.create(
        {
            "group_name": payload.get("group_name") or f"Groupe {siren}",
            "siren": siren,
            "description": payload.get("description"),
            "is_active": True,
        }
    )
    if not row:
        raise RuntimeError("Création du groupe échouée")
    return str(row["id"]), True


def _commit_establishment(
    payload: Dict[str, Any], group_id: Optional[str], action: str
) -> tuple[str, bool]:
    siret = payload.get("siret", "")
    existing = repo.find_company_by_siret(siret)
    client = get_supabase_admin_client()
    insert_data = {
        k: payload[k]
        for k in (
            "company_name",
            "raison_sociale",
            "siret",
            "siren",
            "code_naf",
            "naf_ape",
            "effectif",
            "address",
            "adresse_rue",
            "adresse_code_postal",
            "adresse_ville",
            "is_active",
        )
        if k in payload and payload[k] is not None
    }
    if group_id:
        insert_data["group_id"] = group_id

    if existing:
        cid = str(existing["id"])
        if action == "update":
            client.table("companies").update(insert_data).eq("id", cid).execute()
        elif group_id and not existing.get("group_id"):
            client.table("companies").update({"group_id": group_id}).eq("id", cid).execute()
        return cid, False

    insert_data.setdefault("is_active", True)
    resp = client.table("companies").insert(insert_data).execute()
    if not resp.data:
        raise RuntimeError(f"Création entreprise {siret} échouée")
    return str(resp.data[0]["id"]), True


def _commit_collective_agreement(
    payload: Dict[str, Any], company_by_siret: Dict[str, str]
) -> None:
    siret = payload.get("siret", "")
    idcc = payload.get("idcc", "")
    company_id = company_by_siret.get(siret)
    if not company_id:
        existing = repo.find_company_by_siret(siret)
        company_id = str(existing["id"]) if existing else None
    if not company_id:
        raise RuntimeError(f"Entreprise {siret} introuvable pour IDCC {idcc}")
    agreement_id = repo.resolve_collective_agreement_id(idcc)
    if not agreement_id:
        logger.warning("IDCC %s absent du catalogue — assignation ignorée", idcc)
        return
    repo.upsert_company_collective_agreement(company_id, agreement_id)
    client = get_supabase_admin_client()
    client.table("companies").update({"idcc": idcc}).eq("id", company_id).execute()


def _commit_employee(
    payload: Dict[str, Any],
    source_ref: str,
    company_by_siret: Dict[str, str],
    action: str,
) -> tuple[Optional[str], bool, Optional[Dict[str, Any]]]:
    # source_ref = emp:{siret}:{nir}
    parts = source_ref.split(":")
    siret = parts[1] if len(parts) > 1 else ""
    company_id = company_by_siret.get(siret)
    if not company_id:
        existing_co = repo.find_company_by_siret(siret)
        company_id = str(existing_co["id"]) if existing_co else None
    if not company_id:
        raise RuntimeError(f"Établissement {siret} introuvable pour le salarié")

    nir = payload.get("nir")
    existing = repo.find_employee_by_nir(company_id, nir) if nir else None

    clean_payload = {
        k: v
        for k, v in payload.items()
        if not k.startswith("_") and k not in ("collective_agreement_idcc", "import_source")
    }

    idcc = payload.get("collective_agreement_idcc")
    if idcc:
        agreement_id = repo.resolve_collective_agreement_id(idcc)
        if agreement_id:
            clean_payload["collective_agreement_id"] = agreement_id

    if existing:
        if action == "create":
            action = "update"
        update_employee(str(existing["id"]), clean_payload)
        return str(existing["id"]), False, existing

    row = create_employee_imported(clean_payload, company_id)
    return str(row["id"]), True, row


def _commit_cumul(
    payload: Dict[str, Any],
    company_by_siret: Dict[str, str],
    employee_by_ref: Dict[str, Dict[str, Any]],
) -> None:
    siret = payload.get("siret", "")
    nir = payload.get("nir", "")
    month = int(payload.get("month", 0))
    document = payload.get("cumuls_document") or {}

    company_id = company_by_siret.get(siret)
    if not company_id:
        co = repo.find_company_by_siret(siret)
        company_id = str(co["id"]) if co else None
    if not company_id:
        raise RuntimeError(f"Entreprise {siret} introuvable pour cumuls")

    emp = repo.find_employee_by_nir(company_id, nir)
    if not emp:
        ref = f"emp:{siret}:{nir}"
        emp = employee_by_ref.get(ref)
    if not emp or not emp.get("employee_folder_name"):
        raise RuntimeError(f"Salarié NIR {nir} introuvable pour cumuls")

    write_cumuls_file(str(emp["employee_folder_name"]), month, document)
