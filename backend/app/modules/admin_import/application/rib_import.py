"""Cas d'usage import RIB depuis Excel."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.modules.admin_import.application.rib_excel import (
    detect_rib_column_mapping,
    read_tabular_file,
    row_value,
)
from app.modules.admin_import.application.rib_parser import (
    build_coordonnees_bancaires,
    parse_rib_cell,
)
from app.modules.admin_import.infrastructure import repository as repo
from app.modules.admin_import.schemas.requests import RibImportCommitBody
from app.modules.employees.application import commands as employee_commands
from app.modules.schedules.application.employee_match import resolve_employee_for_timesheet
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


def _match_by_email(
    email: str,
    employees: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    target = email.strip().lower()
    if not target:
        return None
    matches = [
        e for e in employees if (e.get("email") or "").strip().lower() == target
    ]
    return matches[0] if len(matches) == 1 else None


def _match_by_names(
    first_name: str,
    last_name: str,
    employees: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    fn = first_name.strip().lower()
    ln = last_name.strip().lower()
    if not fn or not ln:
        return None
    matches = [
        e
        for e in employees
        if (e.get("first_name") or "").strip().lower() == fn
        and (e.get("last_name") or "").strip().lower() == ln
    ]
    return matches[0] if len(matches) == 1 else None


def _identity_label(
    *,
    matricule: str,
    email: str,
    first_name: str,
    last_name: str,
    full_name: str,
) -> str:
    if first_name and last_name:
        return f"{first_name} {last_name}".strip()
    if full_name:
        return full_name
    if email:
        return email
    if matricule:
        return f"Matricule {matricule}"
    return ""


def _resolve_row_match(
    *,
    roster: List[RosterEmployee],
    employees: List[Dict[str, Any]],
    matricule: str,
    email: str,
    first_name: str,
    last_name: str,
    full_name: str,
) -> Dict[str, Any]:
    """Retourne employee_id, matched_name, confidence, method, review_status, warnings."""
    warnings: List[str] = []

    if email:
        email_match = _match_by_email(email, employees)
        if email_match:
            return {
                "employee_id": str(email_match["id"]),
                "matched_name": f"{email_match.get('first_name', '')} {email_match.get('last_name', '')}".strip(),
                "match_confidence": "high",
                "match_method": "email",
                "review_status": "ok",
                "warnings": warnings,
            }
        if email:
            warnings.append(f"Aucun employé avec l'email « {email} ».")

    if first_name and last_name:
        name_match = _match_by_names(first_name, last_name, employees)
        if name_match:
            return {
                "employee_id": str(name_match["id"]),
                "matched_name": f"{name_match.get('first_name', '')} {name_match.get('last_name', '')}".strip(),
                "match_confidence": "high",
                "match_method": "name_exact",
                "review_status": "ok",
                "warnings": warnings,
            }
        warnings.append(
            f"Aucune correspondance exacte pour « {first_name} {last_name} »."
        )

    raw_name = full_name or _identity_label(
        matricule=matricule,
        email=email,
        first_name=first_name,
        last_name=last_name,
        full_name=full_name,
    )
    proposal = resolve_employee_for_timesheet(
        raw_name=raw_name,
        matricule=matricule or None,
        roster=roster,
    )
    return {
        "employee_id": proposal.employee_id,
        "matched_name": proposal.matched_name,
        "match_confidence": proposal.match_confidence or "none",
        "match_method": proposal.match_method or "none",
        "review_status": proposal.review_status or "error",
        "warnings": warnings + list(proposal.warnings),
    }


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
            "Colonne « RIB » introuvable. Le fichier doit contenir une colonne nommée RIB (ou IBAN)."
        )

    employees = repo.list_company_employees(company_id)
    roster = _build_roster(employees)
    by_id = _employees_by_id(employees)

    previews: List[Dict[str, Any]] = []
    summary = {"total": 0, "ready": 0, "warning": 0, "error": 0}

    for idx, row in enumerate(sheet.rows, start=2):
        rib_raw = row_value(row, mapping.get("rib"))
        if not rib_raw:
            continue

        matricule = row_value(row, mapping.get("matricule"))
        email = row_value(row, mapping.get("email"))
        first_name = row_value(row, mapping.get("first_name"))
        last_name = row_value(row, mapping.get("last_name"))
        full_name = row_value(row, mapping.get("full_name"))
        bic_hint = row_value(row, mapping.get("bic"))

        iban, bic, iban_valid, rib_error = parse_rib_cell(rib_raw, bic_hint=bic_hint)
        match = _resolve_row_match(
            roster=roster,
            employees=employees,
            matricule=matricule,
            email=email,
            first_name=first_name,
            last_name=last_name,
            full_name=full_name,
        )

        review_status = match["review_status"]
        warnings = list(match["warnings"])
        if rib_error:
            warnings.append(rib_error)
            review_status = "error"
        elif not iban_valid:
            review_status = "error"
        elif match["employee_id"] and review_status == "ok" and iban_valid:
            pass
        elif match["employee_id"] and iban_valid and review_status == "warning":
            pass
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

        item = {
            "row_index": idx,
            "raw_identity": _identity_label(
                matricule=matricule,
                email=email,
                first_name=first_name,
                last_name=last_name,
                full_name=full_name,
            ),
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
