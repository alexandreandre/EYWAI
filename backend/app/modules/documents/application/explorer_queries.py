"""Agrégation documents entreprise (explorateur RH)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.core.database import supabase
from app.modules.documents.infrastructure.repository import documents_repository
from app.modules.employee_exits.domain.document_access import (
    rh_should_list_in_documents_explorer,
)
from app.modules.employees.application.service import enrich_employee_with_exit_context
from app.modules.payslips.infrastructure.storage_urls import create_payslip_url_maps
from app.modules.employees.infrastructure.providers import get_storage_provider


def _data(resp: Any) -> Any:
    return resp.data if resp else None


def _list(resp: Any) -> List[Dict[str, Any]]:
    d = _data(resp)
    if d is None:
        return []
    return d if isinstance(d, list) else [d]


def _employee_display_name(row: Dict[str, Any]) -> str:
    fn = (row.get("first_name") or "").strip()
    ln = (row.get("last_name") or "").strip()
    full = f"{fn} {ln}".strip()
    return full or str(row.get("id") or "Collaborateur")


def _fetch_company_payslips(company_id: str) -> List[Dict[str, Any]]:
    rows = _list(
        supabase.table("payslips")
        .select("id, employee_id, month, year, pdf_storage_path")
        .eq("company_id", company_id)
        .order("year", desc=True)
        .order("month", desc=True)
        .execute()
    )
    if not rows:
        return []

    emp_ids = list({str(r["employee_id"]) for r in rows if r.get("employee_id")})
    names: Dict[str, str] = {}
    for eid in emp_ids:
        er = (
            supabase.table("employees")
            .select("id, first_name, last_name")
            .eq("id", eid)
            .maybe_single()
            .execute()
        )
        ed = _data(er)
        if ed:
            names[eid] = _employee_display_name(ed)

    paths = [p["pdf_storage_path"] for p in rows if p.get("pdf_storage_path")]
    if not paths:
        return []

    download_map, preview_map = create_payslip_url_maps(paths, 3600)

    result: List[Dict[str, Any]] = []
    for p in rows:
        storage_path = p.get("pdf_storage_path")
        eid = str(p.get("employee_id") or "")
        if not storage_path or storage_path not in download_map or not eid:
            continue
        result.append(
            {
                "id": str(p["id"]),
                "employee_id": eid,
                "employee_name": names.get(eid) or eid,
                "name": storage_path.split("/")[-1],
                "url": download_map[storage_path],
                "preview_url": preview_map.get(storage_path, ""),
                "month": int(p["month"]),
                "year": int(p["year"]),
            }
        )
    return result


def _identity_label(emp: Dict[str, Any]) -> str:
    if emp.get("is_subject_to_residence_permit"):
        return "Titre de séjour"
    return "Carte d'identité / Passeport"


def _build_employees_index(
    emp_rows: List[Dict[str, Any]],
) -> tuple[Dict[str, Dict[str, Any]], set[str]]:
    employees: Dict[str, Dict[str, Any]] = {}
    visible_employee_ids: set[str] = set()

    for row in emp_rows:
        if not row.get("id"):
            continue
        enriched = enrich_employee_with_exit_context(dict(row))
        employee_id = str(enriched["id"])
        employees[employee_id] = enriched
        user_id = enriched.get("user_id")
        if user_id:
            employees.setdefault(str(user_id), enriched)
        if rh_should_list_in_documents_explorer(enriched):
            visible_employee_ids.add(employee_id)

    return employees, visible_employee_ids


def _filter_rows_for_visible_employees(
    rows: List[Dict[str, Any]],
    visible_employee_ids: set[str],
    *,
    employee_id_key: str = "employee_id",
) -> List[Dict[str, Any]]:
    return [
        row
        for row in rows
        if str(row.get(employee_id_key) or "") in visible_employee_ids
    ]


def _scan_storage_bucket(
    bucket: str,
    company_id: str,
    employees: Dict[str, Dict[str, Any]],
    visible_employee_ids: set[str],
    *,
    kind: str,
    file_resolver,
) -> List[Dict[str, Any]]:
    storage = get_storage_provider()
    items: List[Dict[str, Any]] = []
    roots = storage.list_files(bucket, company_id)
    for folder in roots:
        emp_id = str(folder.get("name") or "")
        if not emp_id:
            continue
        if emp_id not in visible_employee_ids:
            continue
        emp = employees.get(emp_id)
        if not emp:
            continue
        inner = storage.list_files(bucket, f"{company_id}/{emp_id}")
        resolved = file_resolver(inner, emp)
        if not resolved:
            continue
        file_name, label = resolved
        storage_path = f"{company_id}/{emp_id}/{file_name}"
        url = storage.create_signed_url(
            bucket,
            storage_path,
            expiry_seconds=3600,
            download=True,
        )
        preview_url = storage.create_signed_url(
            bucket,
            storage_path,
            expiry_seconds=3600,
            download=False,
        )
        if not url or not preview_url:
            continue
        items.append(
            {
                "employee_id": emp_id,
                "employee_name": _employee_display_name(emp),
                "kind": kind,
                "url": url,
                "preview_url": preview_url,
                "label": label,
            }
        )
    return items


def get_documents_explorer(company_id: str) -> Dict[str, Any]:
    """Liste agrégée pour l'explorateur documents RH (générés, bulletins, fichiers stockage)."""
    from app.modules.employees.infrastructure.repository import EmployeeRepository

    emp_rows = EmployeeRepository().get_by_company(company_id)
    employees, visible_employee_ids = _build_employees_index(emp_rows)

    generated = _filter_rows_for_visible_employees(
        documents_repository.get_all(company_id),
        visible_employee_ids,
    )
    payslips = _filter_rows_for_visible_employees(
        _fetch_company_payslips(company_id),
        visible_employee_ids,
    )

    storage: List[Dict[str, Any]] = []

    def contract_resolver(inner: List[Dict[str, Any]], _emp: Dict[str, Any]) -> Optional[tuple[str, str]]:
        if any(f.get("name") == "contrat.pdf" for f in inner):
            return ("contrat.pdf", "Contrat de travail (fichier signé)")
        return None

    storage.extend(
        _scan_storage_bucket(
            "contracts",
            company_id,
            employees,
            visible_employee_ids,
            kind="contract",
            file_resolver=contract_resolver,
        )
    )

    def identity_resolver(inner: List[Dict[str, Any]], emp: Dict[str, Any]) -> Optional[tuple[str, str]]:
        for ext in [".pdf", ".jpg", ".jpeg", ".png"]:
            name = f"piece_identite{ext}"
            if any(f.get("name") == name for f in inner):
                return (name, _identity_label(emp))
        return None

    storage.extend(
        _scan_storage_bucket(
            "piece_identite",
            company_id,
            employees,
            visible_employee_ids,
            kind="identity",
            file_resolver=identity_resolver,
        )
    )

    def credentials_resolver(inner: List[Dict[str, Any]], _emp: Dict[str, Any]) -> Optional[tuple[str, str]]:
        if any(f.get("name") == "creation_compte.pdf" for f in inner):
            return ("creation_compte.pdf", "Identifiants de connexion")
        return None

    storage.extend(
        _scan_storage_bucket(
            "creation_compte",
            company_id,
            employees,
            visible_employee_ids,
            kind="credentials",
            file_resolver=credentials_resolver,
        )
    )

    return {
        "generated": generated,
        "payslips": payslips,
        "storage": storage,
    }
