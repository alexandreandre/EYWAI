"""Cas d'usage import dates d'ancienneté (reprise / prime) depuis Excel."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.modules.admin_import.application.rib_matching import (
    _row_identity_fields,
    resolve_rib_row_match,
)
from app.modules.admin_import.application.seniority_excel import (
    detect_seniority_column_mapping,
    parse_seniority_date_cell,
    read_seniority_tabular_file,
    row_value,
)
from app.modules.admin_import.application.seniority_row_filter import (
    should_skip_seniority_row,
)
from app.modules.admin_import.infrastructure import repository as repo
from app.modules.admin_import.schemas.requests import SeniorityImportCommitBody
from app.modules.employees.application import commands as employee_commands
from app.modules.schedules.schemas.ai import RosterEmployee


def _build_roster(employees: List[Dict[str, Any]]) -> List[RosterEmployee]:
    return [
        RosterEmployee(
            id=str(emp["id"]),
            first_name=str(emp.get("first_name") or ""),
            last_name=str(emp.get("last_name") or ""),
            time_tracking_id=emp.get("time_tracking_id"),
        )
        for emp in employees
    ]


def _employees_by_id(employees: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    return {str(e["id"]): e for e in employees}


def _list_employees_for_seniority(company_id: str) -> List[Dict[str, Any]]:
    base = repo.list_company_employees(company_id)
    if not base:
        return []
    try:
        from app.core.database import get_supabase_admin_client

        client = get_supabase_admin_client()
        ids = [str(e["id"]) for e in base]
        extra: Dict[str, Dict[str, Any]] = {}
        chunk = 100
        for i in range(0, len(ids), chunk):
            batch_ids = ids[i : i + chunk]
            resp = (
                client.table("employees")
                .select(
                    "id, hire_date, seniority_reference_date, statut, "
                    "classification_conventionnelle"
                )
                .in_("id", batch_ids)
                .execute()
            )
            for row in resp.data or []:
                extra[str(row["id"])] = row
        merged: List[Dict[str, Any]] = []
        for emp in base:
            row = dict(emp)
            row.update(extra.get(str(emp["id"]), {}))
            merged.append(row)
        return merged
    except Exception:
        return base


def _employee_classe(emp: Dict[str, Any]) -> Optional[int]:
    cc = emp.get("classification_conventionnelle") or {}
    if not isinstance(cc, dict):
        return None
    for key in ("classe_emploi", "classe", "coefficient"):
        raw = cc.get(key)
        if raw is not None:
            try:
                return int(float(raw))
            except (TypeError, ValueError):
                continue
    return None


def _active_employees(employees: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [
        e
        for e in employees
        if (e.get("employment_status") or "actif").lower() in ("actif", "active")
    ]


def _missing_active_employees(
    employees: List[Dict[str, Any]],
    matched_ids: set[str],
) -> List[Dict[str, str]]:
    missing: List[Dict[str, str]] = []
    for emp in _active_employees(employees):
        emp_id = str(emp["id"])
        if emp_id in matched_ids:
            continue
        raw_ref = emp.get("seniority_reference_date")
        raw_hire = emp.get("hire_date")
        missing.append(
            {
                "employee_id": emp_id,
                "first_name": str(emp.get("first_name") or ""),
                "last_name": str(emp.get("last_name") or ""),
                "current_seniority_date": str(raw_ref)[:10] if raw_ref else None,
                "current_hire_date": str(raw_hire)[:10] if raw_hire else None,
            }
        )
    missing.sort(key=lambda e: (e["last_name"].upper(), e["first_name"].upper()))
    return missing


def _normalize_statut(value: str) -> str:
    return (value or "").strip().lower().replace("-", " ").replace("_", " ")


def parse_seniority_import_file(
    content: bytes,
    filename: str,
    company_id: str,
) -> Dict[str, Any]:
    company = repo.find_company(company_id)
    if not company:
        raise LookupError("Entreprise introuvable.")

    sheet = read_seniority_tabular_file(content, filename)
    if not sheet.headers:
        raise ValueError("Fichier vide ou sans en-têtes.")

    mapping = detect_seniority_column_mapping(sheet.headers)
    if "seniority_date" not in mapping:
        raise ValueError(
            "Colonne « Date ancienneté » introuvable. "
            f"En-têtes détectés : {', '.join(sheet.headers[:8])}…"
        )
    if not mapping.get("last_name") and not mapping.get("first_name"):
        raise ValueError(
            "Colonnes NOM et PRENOM introuvables — impossible d'identifier les salariés."
        )

    employees = _list_employees_for_seniority(company_id)
    if not employees:
        raise ValueError(
            "Aucun salarié trouvé pour cette entreprise. Importez d'abord les effectifs."
        )

    roster = _build_roster(employees)
    by_id = _employees_by_id(employees)

    previews: List[Dict[str, Any]] = []
    summary = {
        "total": 0,
        "ready": 0,
        "warning": 0,
        "error": 0,
        "unchanged": 0,
        "skipped_junk": 0,
    }
    data_start_line = sheet.header_row_index + 1

    for offset, row in enumerate(sheet.rows):
        last_name = row_value(row, mapping.get("last_name"))
        first_name = row_value(row, mapping.get("first_name"))
        full_name = row_value(row, mapping.get("full_name"))
        matricule = row_value(row, mapping.get("matricule"))
        date_raw = row_value(row, mapping.get("seniority_date"))
        statut_raw = row_value(row, mapping.get("statut"))
        classe_raw = row_value(row, mapping.get("classe"))

        fn, ln, _full, identity, _mat = _row_identity_fields(
            matricule=matricule,
            email="",
            first_name=first_name,
            last_name=last_name,
            full_name=full_name,
        )
        if should_skip_seniority_row(
            first_name=fn,
            last_name=ln,
            full_name=full_name,
            identity=identity,
            matricule=matricule,
            row=row,
        ):
            summary["skipped_junk"] += 1
            continue

        parsed_date = parse_seniority_date_cell(date_raw)
        warnings: List[str] = []

        match = resolve_rib_row_match(
            roster=roster,
            employees=employees,
            matricule=matricule,
            email="",
            first_name=fn,
            last_name=ln,
            full_name=full_name or identity,
        )
        review_status = match["review_status"]
        warnings.extend(match["warnings"])

        if not parsed_date:
            if date_raw:
                warnings.append(f"Date illisible : « {date_raw} ».")
            review_status = "error"
        elif not match.get("employee_id"):
            review_status = "error"
            if not warnings:
                warnings.append("Employé non identifié — associez manuellement.")

        current_date: Optional[str] = None
        current_hire: Optional[str] = None
        emp_id = match.get("employee_id")
        if emp_id and emp_id in by_id:
            emp = by_id[emp_id]
            raw_ref = emp.get("seniority_reference_date")
            if raw_ref:
                current_date = str(raw_ref)[:10]
            raw_hire = emp.get("hire_date")
            if raw_hire:
                current_hire = str(raw_hire)[:10]

            if statut_raw and emp.get("statut"):
                file_cadre = "cadre" in _normalize_statut(statut_raw)
                emp_cadre = "cadre" in _normalize_statut(str(emp.get("statut")))
                if not file_cadre == emp_cadre and _normalize_statut(statut_raw) != _normalize_statut(
                    str(emp.get("statut"))
                ):
                    warnings.append(
                        f"Statut fichier ({statut_raw}) ≠ fiche ({emp.get('statut')})."
                    )
                    if review_status == "ok":
                        review_status = "warning"

            if classe_raw:
                try:
                    classe_file = int(float(classe_raw.replace(",", ".")))
                    classe_emp = _employee_classe(emp)
                    if classe_emp is not None and classe_file != classe_emp:
                        warnings.append(
                            f"Classe fichier ({classe_file}) ≠ fiche ({classe_emp})."
                        )
                        if review_status == "ok":
                            review_status = "warning"
                except (TypeError, ValueError):
                    warnings.append(f"Classe illisible : « {classe_raw} ».")

        unchanged = bool(parsed_date and current_date == parsed_date)
        if unchanged and review_status == "ok":
            review_status = "warning"
            warnings.append("Date identique à la fiche — aucune modification nécessaire.")

        line_no = data_start_line + offset + 1
        item = {
            "row_index": line_no,
            "raw_identity": identity,
            "matricule": matricule or None,
            "seniority_date_raw": date_raw,
            "seniority_date": parsed_date,
            "employee_id": match.get("employee_id"),
            "matched_name": match.get("matched_name"),
            "match_confidence": match.get("match_confidence") or "none",
            "match_method": match.get("match_method") or "none",
            "review_status": review_status,
            "warnings": warnings,
            "current_seniority_date": current_date,
            "current_hire_date": current_hire,
            "unchanged": unchanged,
            "raw_row": row,
        }
        previews.append(item)
        summary["total"] += 1
        if unchanged:
            summary["unchanged"] += 1
        if review_status == "ok":
            summary["ready"] += 1
        elif review_status == "warning":
            summary["warning"] += 1
        else:
            summary["error"] += 1

    matched_ids = {
        str(item["employee_id"])
        for item in previews
        if item.get("employee_id")
    }
    active_count = len(_active_employees(employees))
    missing = _missing_active_employees(employees, matched_ids)
    summary["active_employees"] = active_count
    summary["matched_employees"] = len(matched_ids)
    summary["missing_employees"] = len(missing)

    return {
        "company_id": company_id,
        "company_name": company.get("company_name") or "",
        "headers": sheet.headers,
        "column_mapping": mapping,
        "rows": previews,
        "missing_employees": missing,
        "roster": [
            {
                "id": e.id,
                "first_name": e.first_name,
                "last_name": e.last_name,
                "time_tracking_id": e.time_tracking_id,
            }
            for e in roster
        ],
        "summary": summary,
    }


def commit_seniority_import(body: SeniorityImportCommitBody) -> Dict[str, Any]:
    company = repo.find_company(body.company_id)
    if not company:
        raise LookupError("Entreprise introuvable.")

    employees = _list_employees_for_seniority(body.company_id)
    allowed_ids = {str(e["id"]) for e in employees}

    applied = 0
    skipped = 0
    results: List[Dict[str, Any]] = []
    errors: List[str] = []

    for row in body.rows:
        if not row.confirmed:
            skipped += 1
            continue
        if row.employee_id not in allowed_ids:
            skipped += 1
            errors.append(f"Ligne {row.row_index} : employé hors entreprise.")
            continue
        if not row.seniority_date:
            skipped += 1
            errors.append(f"Ligne {row.row_index} : date d'ancienneté manquante.")
            continue

        try:
            updated = employee_commands.update_employee(
                row.employee_id,
                {"seniority_reference_date": row.seniority_date},
            )
            applied += 1
            results.append(
                {
                    "row_index": row.row_index,
                    "employee_id": row.employee_id,
                    "success": True,
                    "message": (
                        f"Date enregistrée pour "
                        f"{updated.get('first_name', '')} {updated.get('last_name', '')}".strip()
                    ),
                }
            )
        except Exception as exc:
            skipped += 1
            msg = f"Ligne {row.row_index} : {exc}"
            errors.append(msg)
            results.append(
                {
                    "row_index": row.row_index,
                    "employee_id": row.employee_id,
                    "success": False,
                    "message": str(exc),
                }
            )

    return {
        "applied": applied,
        "skipped": skipped,
        "results": results,
        "errors": errors,
    }
