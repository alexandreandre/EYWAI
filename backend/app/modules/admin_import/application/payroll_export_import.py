"""Cas d'usage import export paie salariés (enrichissement Quadra)."""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

from app.modules.admin_import.application.payroll_export_mapping import (
    detect_payroll_export_column_mapping,
    normalize_nir,
)
from app.modules.admin_import.application.payroll_export_matching import (
    resolve_payroll_export_row_match,
)
from app.modules.admin_import.application.payroll_export_parser import (
    coerce_email_and_phone,
    is_dsn_placeholder_email,
    parse_payroll_export_row,
    read_payroll_export_file,
)
from app.modules.admin_import.application.rib_excel import row_value
from app.modules.admin_import.application.rib_import import _build_roster, _employees_by_id
from app.modules.admin_import.application.payroll_export_preview import (
    build_preview_field_list,
)
from app.modules.admin_import.application.payroll_export_teams import (
    mod_moi_team_mapping_info,
    resolve_mod_moi_team_mapping,
)
from app.modules.admin_import.infrastructure import repository as repo
from app.modules.admin_import.schemas.requests import PayrollExportCommitBody
from app.modules.employees.application import commands as employee_commands
from app.modules.oeth_settings.application.commands import save_employee_boeth
from app.modules.oeth_settings.schemas.requests import EmployeeBoethUpdate
from app.modules.teams.application.commands import assign_employee_to_team, create_team
from app.modules.teams.infrastructure.repository import teams_repository
from app.modules.teams.schemas.requests import TeamCreate
from app.shared.utils.iban import mask_iban


def _get_or_create_team(company_id: str, team_name: str) -> str:
    teams = teams_repository.get_teams_by_company(company_id)
    for t in teams:
        if (t.get("name") or "").strip().upper() == team_name.upper():
            return str(t["id"])
    row = create_team(
        TeamCreate(name=team_name, description=f"Import export paie — {team_name}"),
        company_id,
    )
    return str(row["id"])


def _email_conflict(
    email: str,
    employee_id: Optional[str],
    employees: List[Dict[str, Any]],
) -> Optional[str]:
    if not email or is_dsn_placeholder_email(email):
        return None
    target = email.strip().lower()
    others = [
        e
        for e in employees
        if (e.get("email") or "").strip().lower() == target
        and str(e.get("id")) != str(employee_id or "")
    ]
    if others:
        return f"Email déjà utilisé par {others[0].get('first_name')} {others[0].get('last_name')}"
    return None


def parse_payroll_export_file(
    content: bytes,
    filename: str,
    company_id: str,
    *,
    map_mod_moi_teams: Optional[bool] = None,
) -> Dict[str, Any]:
    company = repo.find_company(company_id)
    if not company:
        raise LookupError("Entreprise introuvable.")

    sheet = read_payroll_export_file(content, filename)
    if not sheet.headers:
        raise ValueError("Fichier vide ou sans en-têtes.")

    mapping = detect_payroll_export_column_mapping(sheet.headers)
    if "nir" not in mapping and (
        "last_name" not in mapping or "first_name" not in mapping
    ):
        raise ValueError(
            "Colonnes obligatoires introuvables (Numéro Insee ou Nom + Prénom). "
            f"Ligne d'en-tête détectée : {sheet.header_row_index or '—'}."
        )

    employees = repo.list_company_employees(company_id)
    if not employees:
        raise ValueError(
            "Aucun salarié trouvé pour cette entreprise. Importez d'abord les effectifs (DSN)."
        )

    roster = _build_roster(employees)
    by_id = _employees_by_id(employees)
    mapping_info = mod_moi_team_mapping_info(company_id)
    map_teams = resolve_mod_moi_team_mapping(
        company_id,
        explicit=map_mod_moi_teams,
    )

    previews: List[Dict[str, Any]] = []
    summary = {"total": 0, "ready": 0, "warning": 0, "error": 0, "unmatched": 0, "rib_rows": 0, "rib_valid_rows": 0}
    data_start_line = sheet.header_row_index + 1

    for offset, row in enumerate(sheet.rows):
        fn = row_value(row, mapping.get("first_name"))
        ln = row_value(row, mapping.get("last_name"))
        nir = normalize_nir(row_value(row, mapping.get("nir")))
        email = row_value(row, mapping.get("email"))
        phone = row_value(row, mapping.get("phone"))
        email, phone = coerce_email_and_phone(email, phone)
        identifiant = row_value(row, mapping.get("identifiant"))

        if not fn and not ln and not nir:
            continue

        parsed = parse_payroll_export_row(row, mapping, map_mod_moi_teams=map_teams)
        match = resolve_payroll_export_row_match(
            roster=roster,
            employees=employees,
            nir=nir,
            matricule=identifiant,
            email=email,
            first_name=fn,
            last_name=ln,
            identifiant=identifiant,
        )

        warnings = list(parsed.get("warnings") or []) + list(match.get("warnings") or [])
        review_status = match.get("review_status") or "error"
        emp_id = match.get("employee_id")

        if emp_id:
            conflict = _email_conflict(
                email, emp_id, employees
            ) or _email_conflict(
                (parsed.get("employee_patch") or {}).get("email") or "", emp_id, employees
            )
            if conflict:
                warnings.append(conflict)
                review_status = "error"
        else:
            summary["unmatched"] += 1

        current_email = None
        current_team = None
        if emp_id and emp_id in by_id:
            emp = by_id[emp_id]
            current_email = emp.get("email")
            current_team = emp.get("team_id")

        line_no = data_start_line + offset + 1
        patch = parsed.get("employee_patch") or {}
        preview_cols = dict(parsed.get("preview") or {})
        iban = (patch.get("coordonnees_bancaires") or {}).get("iban")
        if iban:
            summary["rib_rows"] += 1
            from app.shared.utils.iban import has_valid_iban

            if has_valid_iban({"iban": iban}):
                summary["rib_valid_rows"] += 1
            preview_cols["iban_masked"] = mask_iban(iban)

        item = {
            "row_index": line_no,
            "raw_identity": parsed.get("raw_identity") or f"{fn} {ln}".strip(),
            "nir": nir or None,
            "email": email or None,
            "phone": phone or None,
            "employee_id": emp_id,
            "matched_name": match.get("matched_name"),
            "match_confidence": match.get("match_confidence") or "none",
            "match_method": match.get("match_method") or "none",
            "review_status": review_status,
            "warnings": warnings,
            "preview_columns": preview_cols,
            "employee_patch": patch,
            "boeth": parsed.get("boeth"),
            "team_name": parsed.get("team_name"),
            "current_email": current_email,
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
        "mod_moi_team_mapping": map_teams,
        "mod_moi_team_mapping_default": mapping_info["mod_moi_team_mapping_default"],
        "headers": sheet.headers,
        "column_mapping": mapping,
        "preview_fields": build_preview_field_list(mapping, previews),
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


def _merge_email_patch(
    patch: Dict[str, Any],
    current_email: Optional[str],
) -> None:
    new_email = patch.get("email")
    if not new_email:
        patch.pop("email", None)
        return
    if current_email and not is_dsn_placeholder_email(current_email):
        if is_dsn_placeholder_email(new_email):
            patch.pop("email", None)
        elif new_email.strip().lower() == (current_email or "").strip().lower():
            patch.pop("email", None)


def commit_payroll_export(body: PayrollExportCommitBody) -> Dict[str, Any]:
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

    team_cache: Dict[str, str] = {}

    for row in body.rows:
        if not row.confirmed:
            skipped += 1
            continue
        if not row.employee_id or row.employee_id not in allowed_ids:
            skipped += 1
            errors.append(f"Ligne {row.row_index} : employé hors entreprise ou non identifié.")
            continue

        emp = by_id[row.employee_id]
        emp_name = f"{emp.get('first_name', '')} {emp.get('last_name', '')}".strip()
        patch = dict(row.employee_patch or {})

        _merge_email_patch(patch, emp.get("email"))

        if not patch and not row.team_name and not row.boeth:
            skipped += 1
            results.append(
                {
                    "row_index": row.row_index,
                    "employee_id": row.employee_id,
                    "success": False,
                    "message": "Aucune donnée à appliquer.",
                    "duplicate_warnings": [],
                }
            )
            continue

        try:
            duplicate_warnings: List[str] = []
            if patch:
                updated = employee_commands.update_employee(row.employee_id, patch)
                for w in updated.get("warnings") or []:
                    if isinstance(w, str):
                        duplicate_warnings.append(w)

            if row.team_name and body.create_teams_if_missing:
                tname = row.team_name.strip().upper()
                if tname not in team_cache:
                    team_cache[tname] = _get_or_create_team(body.company_id, tname)
                assign_employee_to_team(
                    row.employee_id,
                    team_cache[tname],
                    body.company_id,
                )

            if row.boeth and row.boeth.get("boeth_code"):
                save_employee_boeth(
                    body.company_id,
                    row.employee_id,
                    EmployeeBoethUpdate(
                        boeth_code=row.boeth["boeth_code"],
                        valid_from=date.today(),
                        notes="Import export paie Quadra",
                    ),
                )

            results.append(
                {
                    "row_index": row.row_index,
                    "employee_id": row.employee_id,
                    "success": True,
                    "message": f"Données enregistrées pour {emp_name}.",
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
