"""Cas d'usage import RIB depuis Excel."""

from __future__ import annotations

from typing import Any, Dict, List

from app.modules.admin_import.application.rib_excel import (
    detect_rib_column_mapping,
    read_tabular_file,
    row_value,
)
from app.modules.admin_import.application.rib_matching import (
    resolve_rib_row_match,
    _row_identity_fields,
)
from app.modules.admin_import.application.rib_parser import (
    build_coordonnees_bancaires,
    parse_rib_cell,
)
from app.modules.admin_import.infrastructure import repository as repo
from app.modules.admin_import.schemas.requests import RibImportCommitBody
from app.modules.employees.application import commands as employee_commands
from app.modules.schedules.schemas.ai import RosterEmployee
from app.shared.utils.iban import extract_iban, mask_iban, normalize_iban


def _build_roster(employees: List[Dict[str, Any]]) -> List[RosterEmployee]:
    roster: List[RosterEmployee] = []
    for emp in employees:
        roster.append(
            RosterEmployee(
                id=str(emp["id"]),
                first_name=str(emp.get("first_name") or ""),
                last_name=str(emp.get("last_name") or ""),
                time_tracking_id=emp.get("time_tracking_id"),
            )
        )
    return roster


def _employees_by_id(employees: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    return {str(e["id"]): e for e in employees}


def parse_rib_import_file(
    content: bytes,
    filename: str,
    company_id: str,
) -> Dict[str, Any]:
    company = repo.find_company(company_id)
    if not company:
        raise LookupError("Entreprise introuvable.")

    sheet = read_tabular_file(content, filename)
    if not sheet.headers:
        raise ValueError("Fichier vide ou sans en-têtes.")

    mapping = detect_rib_column_mapping(sheet.headers)
    if "rib" not in mapping:
        raise ValueError(
            "Colonne « RIB » introuvable. Le fichier doit contenir une colonne nommée RIB (ou IBAN), "
            f"éventuellement après des lignes d'en-tête (ligne détectée : {sheet.header_row_index or '—'})."
        )

    employees = repo.list_company_employees(company_id)
    if not employees:
        raise ValueError(
            "Aucun salarié trouvé pour cette entreprise dans EYWAI. "
            "Importez d'abord les effectifs (DSN ou création manuelle)."
        )

    roster = _build_roster(employees)
    by_id = _employees_by_id(employees)

    previews: List[Dict[str, Any]] = []
    summary = {"total": 0, "ready": 0, "warning": 0, "error": 0}
    data_start_line = sheet.header_row_index + 1

    for offset, row in enumerate(sheet.rows):
        rib_raw = row_value(row, mapping.get("rib"))
        if not rib_raw:
            continue

        matricule = row_value(row, mapping.get("matricule"))
        email = row_value(row, mapping.get("email"))
        first_name = row_value(row, mapping.get("first_name"))
        last_name = row_value(row, mapping.get("last_name"))
        full_name = row_value(row, mapping.get("full_name"))
        bic_hint = row_value(row, mapping.get("bic"))

        fn, ln, _full, identity, _mat = _row_identity_fields(
            matricule=matricule,
            email=email,
            first_name=first_name,
            last_name=last_name,
            full_name=full_name,
        )

        iban, bic, iban_valid, rib_error = parse_rib_cell(rib_raw, bic_hint=bic_hint)
        match = resolve_rib_row_match(
            roster=roster,
            employees=employees,
            matricule=matricule,
            email=email,
            first_name=fn,
            last_name=ln,
            full_name=full_name or identity,
        )

        review_status = match["review_status"]
        warnings = list(match["warnings"])
        if rib_error:
            warnings.append(rib_error)
            review_status = "error"
        elif not iban_valid:
            review_status = "error"
            if not any("RIB" in w or "IBAN" in w for w in warnings):
                warnings.append("RIB/IBAN invalide.")
        elif not match["employee_id"]:
            review_status = "error"
            if not warnings:
                warnings.append("Employé non identifié — associez manuellement.")

        current_masked = None
        emp_id = match.get("employee_id")
        if emp_id and emp_id in by_id:
            current_iban = extract_iban(by_id[emp_id].get("coordonnees_bancaires"))
            if current_iban:
                current_masked = mask_iban(current_iban)

        line_no = data_start_line + offset + 1
        item = {
            "row_index": line_no,
            "raw_identity": identity,
            "matricule": matricule or None,
            "email": email or None,
            "rib_raw": rib_raw,
            "iban": iban,
            "bic": bic,
            "iban_valid": iban_valid,
            "employee_id": match.get("employee_id"),
            "matched_name": match.get("matched_name"),
            "match_confidence": match.get("match_confidence") or "none",
            "match_method": match.get("match_method") or "none",
            "review_status": review_status,
            "warnings": warnings,
            "current_iban_masked": current_masked,
            "raw_row": row,
        }
        previews.append(item)
        summary["total"] += 1
        if review_status == "ok":
            summary["ready"] += 1
        elif review_status == "warning":
            summary["warning"] += 1
        else:
            summary["error"] += 1

    return {
        "company_id": company_id,
        "company_name": company.get("company_name") or "Entreprise",
        "headers": sheet.headers,
        "column_mapping": mapping,
        "rows": previews,
        "roster": [
            {
                "id": str(e["id"]),
                "first_name": str(e.get("first_name") or ""),
                "last_name": str(e.get("last_name") or ""),
                "time_tracking_id": e.get("time_tracking_id"),
            }
            for e in employees
        ],
        "summary": summary,
    }


def commit_rib_import(body: RibImportCommitBody) -> Dict[str, Any]:
    company = repo.find_company(body.company_id)
    if not company:
        raise LookupError("Entreprise introuvable.")

    employees = repo.list_company_employees(body.company_id)
    allowed_ids = {str(e["id"]) for e in employees}
    by_id = _employees_by_id(employees)

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

        iban = normalize_iban(row.iban)
        if not iban:
            skipped += 1
            errors.append(f"Ligne {row.row_index} : IBAN manquant.")
            continue

        _, _, iban_valid, rib_error = parse_rib_cell(iban)
        if not iban_valid:
            skipped += 1
            errors.append(f"Ligne {row.row_index} : {rib_error or 'IBAN invalide'}.")
            continue

        coord = build_coordonnees_bancaires(iban, row.bic or "")
        emp = by_id[row.employee_id]
        emp_name = f"{emp.get('first_name', '')} {emp.get('last_name', '')}".strip()

        try:
            updated = employee_commands.update_employee(
                row.employee_id,
                {"coordonnees_bancaires": coord},
            )
            duplicate_warnings: List[str] = []
            for w in (updated.get("warnings") or []):
                if isinstance(w, str):
                    duplicate_warnings.append(w)
            results.append(
                {
                    "row_index": row.row_index,
                    "employee_id": row.employee_id,
                    "success": True,
                    "message": f"RIB enregistré pour {emp_name}.",
                    "duplicate_warnings": duplicate_warnings,
                }
            )
            applied += 1
        except Exception as exc:
            skipped += 1
            errors.append(f"Ligne {row.row_index} : {exc}")
            results.append(
                {
                    "row_index": row.row_index,
                    "employee_id": row.employee_id,
                    "success": False,
                    "message": str(exc),
                    "duplicate_warnings": [],
                }
            )

    return {
        "applied": applied,
        "skipped": skipped,
        "results": results,
        "errors": errors,
    }
