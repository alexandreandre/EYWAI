"""Import idempotent classification MOI/MOD pour Mont Blanc Composite."""

from __future__ import annotations

import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.modules.admin_import.application.payroll_export_mapping import (
    detect_payroll_export_column_mapping,
)
from app.modules.admin_import.application.payroll_export_parser import (
    map_service_to_team_name,
    read_payroll_export_file,
)
from app.modules.admin_import.application.rib_excel import row_value
from app.modules.admin_import.infrastructure import repository as repo
from app.modules.teams.application.commands import assign_employee_to_team, create_team
from app.modules.teams.infrastructure.repository import teams_repository
from app.modules.teams.schemas.requests import TeamCreate

_MOD_MOI_TEAM_NAMES = ("MOI", "MOD")
_MBC_COMPANY_NAMES = ("Mont Blanc Composite", "MBC")
_DEFAULT_XLSX_RELATIVE = Path("Config/MBC/Enrichissement Salarié/paie MBC.xlsx")


def normalize_person_name(value: str) -> str:
    """Normalise un nom/prénom (unicode NFKD, sans accents, casefold)."""
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(c for c in text if not unicodedata.combining(c))
    return " ".join(text.casefold().split())


def default_mbc_xlsx_path(repo_root: Optional[Path] = None) -> Path:
    root = repo_root or Path(__file__).resolve().parents[5]
    return root / _DEFAULT_XLSX_RELATIVE


def resolve_mbc_company_id(company_id: Optional[str] = None) -> Dict[str, Any]:
    """Résout l'entreprise MBC (Mont Blanc Composite) via service role."""
    if company_id:
        company = repo.find_company(company_id)
        if not company:
            raise LookupError(f"Entreprise introuvable : {company_id}.")
        return company

    for name in _MBC_COMPANY_NAMES:
        company = repo.find_company_by_normalized_name(name)
        if company:
            return company

    raise LookupError(
        "Entreprise Mont Blanc Composite introuvable. "
        "Indiquez --company-id explicitement."
    )


def _list_active_employees_with_team(company_id: str) -> List[Dict[str, Any]]:
    employees = repo.list_company_employees(company_id)
    if not employees:
        return []

    try:
        from app.core.database import get_supabase_admin_client

        client = get_supabase_admin_client()
        ids = [str(e["id"]) for e in employees]
        extra: Dict[str, Dict[str, Any]] = {}
        chunk = 100
        for i in range(0, len(ids), chunk):
            batch_ids = ids[i : i + chunk]
            resp = (
                client.table("employees")
                .select("id, team_id")
                .in_("id", batch_ids)
                .execute()
            )
            for row in resp.data or []:
                extra[str(row["id"])] = row
        merged: List[Dict[str, Any]] = []
        for emp in employees:
            status = (emp.get("employment_status") or "actif").lower()
            if status not in ("actif", "active"):
                continue
            row = dict(emp)
            row.update(extra.get(str(emp["id"]), {}))
            merged.append(row)
        return merged
    except Exception:
        return [
            e
            for e in employees
            if (e.get("employment_status") or "actif").lower() in ("actif", "active")
        ]


def match_employee_by_name(
    first_name: str,
    last_name: str,
    employees: List[Dict[str, Any]],
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Rapprochement strict par prénom + nom normalisés. Ne devine jamais."""
    fn = normalize_person_name(first_name)
    ln = normalize_person_name(last_name)
    if not fn or not ln:
        return None, "missing_name"

    matches = [
        e
        for e in employees
        if normalize_person_name(e.get("first_name") or "") == fn
        and normalize_person_name(e.get("last_name") or "") == ln
    ]
    if len(matches) == 1:
        return matches[0], None
    if len(matches) > 1:
        return None, "ambiguous"
    return None, "not_found"


def parse_mbc_mod_moi_rows(content: bytes, filename: str) -> List[Dict[str, Any]]:
    """Extrait les lignes éligibles (sans date de sortie, avec équipe MOI/MOD)."""
    sheet = read_payroll_export_file(content, filename)
    if not sheet.headers:
        raise ValueError("Fichier vide ou sans en-têtes.")

    mapping = detect_payroll_export_column_mapping(sheet.headers)
    if "last_name" not in mapping or "first_name" not in mapping:
        raise ValueError(
            "Colonnes Nom / Prénom introuvables dans le fichier export paie."
        )
    if "service" not in mapping:
        raise ValueError("Colonne Service introuvable dans le fichier export paie.")

    rows: List[Dict[str, Any]] = []
    for offset, row in enumerate(sheet.rows):
        first_name = row_value(row, mapping.get("first_name"))
        last_name = row_value(row, mapping.get("last_name"))
        service = row_value(row, mapping.get("service"))
        exit_date = row_value(row, mapping.get("exit_date"))

        if not first_name and not last_name:
            continue

        team_name = map_service_to_team_name(service)
        rows.append(
            {
                "line_number": sheet.header_row_index + 1 + offset,
                "first_name": first_name,
                "last_name": last_name,
                "service": service.strip(),
                "service_normalized": (service or "").strip().upper(),
                "exit_date": exit_date.strip(),
                "team_name": team_name,
            }
        )
    return rows


def _ensure_mod_moi_teams(
    company_id: str,
    *,
    dry_run: bool,
) -> Dict[str, Dict[str, Any]]:
    existing = teams_repository.get_teams_by_company(company_id)
    by_name: Dict[str, Dict[str, Any]] = {}
    for team in existing:
        name = (team.get("name") or "").strip().upper()
        if name in _MOD_MOI_TEAM_NAMES:
            by_name[name] = team

    result: Dict[str, Dict[str, Any]] = {}
    for team_name in _MOD_MOI_TEAM_NAMES:
        if team_name in by_name:
            result[team_name] = {
                "id": str(by_name[team_name]["id"]),
                "created": False,
                "name": team_name,
            }
            continue

        if dry_run:
            result[team_name] = {
                "id": None,
                "created": True,
                "name": team_name,
            }
            continue

        created = create_team(
            TeamCreate(
                name=team_name,
                description=f"Classification MOI/MOD — import MBC ({team_name})",
            ),
            company_id,
        )
        result[team_name] = {
            "id": str(created["id"]),
            "created": True,
            "name": team_name,
        }
    return result


def run_mbc_mod_moi_teams_import(
    *,
    content: bytes,
    filename: str,
    company_id: Optional[str] = None,
    dry_run: bool = True,
) -> Dict[str, Any]:
    """Dry-run ou application de l'affectation team_id MOI/MOD pour MBC."""
    company = resolve_mbc_company_id(company_id)
    resolved_company_id = str(company["id"])

    parsed_rows = parse_mbc_mod_moi_rows(content, filename)
    employees = _list_active_employees_with_team(resolved_company_id)
    if not employees:
        raise ValueError(
            "Aucun salarié actif trouvé pour cette entreprise dans EYWAI."
        )

    teams = _ensure_mod_moi_teams(resolved_company_id, dry_run=dry_run)

    summary: Dict[str, int] = {
        "rows_total": len(parsed_rows),
        "rows_with_exit_date": 0,
        "rows_without_team_mapping": 0,
        "rows_eligible": 0,
        "team_moi": 0,
        "team_mod": 0,
        "source_service_moi": 0,
        "source_service_mod": 0,
        "source_service_cad": 0,
        "matched": 0,
        "unmatched": 0,
        "ambiguous": 0,
        "already_correct": 0,
        "would_assign": 0,
        "would_reassign": 0,
        "assigned": 0,
        "teams_created": 0,
    }
    unmatched: List[Dict[str, Any]] = []
    ambiguous: List[Dict[str, Any]] = []
    assignments: List[Dict[str, Any]] = []

    for row in parsed_rows:
        if row["exit_date"]:
            summary["rows_with_exit_date"] += 1
            continue

        team_name = row["team_name"]
        if not team_name:
            summary["rows_without_team_mapping"] += 1
            continue

        service_norm = row["service_normalized"]
        if service_norm == "MOI":
            summary["source_service_moi"] += 1
        elif service_norm == "MOD":
            summary["source_service_mod"] += 1
        elif service_norm == "CAD":
            summary["source_service_cad"] += 1

        summary["rows_eligible"] += 1
        if team_name == "MOI":
            summary["team_moi"] += 1
        elif team_name == "MOD":
            summary["team_mod"] += 1

        employee, reason = match_employee_by_name(
            row["first_name"],
            row["last_name"],
            employees,
        )
        if reason == "ambiguous":
            summary["ambiguous"] += 1
            summary["unmatched"] += 1
            ambiguous.append(
                {
                    "line_number": row["line_number"],
                    "first_name": row["first_name"],
                    "last_name": row["last_name"],
                    "service": row["service"],
                    "team_name": team_name,
                    "reason": "ambiguous",
                }
            )
            continue

        if employee is None:
            summary["unmatched"] += 1
            unmatched.append(
                {
                    "line_number": row["line_number"],
                    "first_name": row["first_name"],
                    "last_name": row["last_name"],
                    "service": row["service"],
                    "team_name": team_name,
                    "reason": reason or "not_found",
                }
            )
            continue

        summary["matched"] += 1
        team_info = teams[team_name]
        target_team_id = team_info.get("id")
        current_team_id = employee.get("team_id")
        employee_id = str(employee["id"])

        assignment = {
            "employee_id": employee_id,
            "first_name": row["first_name"],
            "last_name": row["last_name"],
            "service": row["service"],
            "team_name": team_name,
            "current_team_id": str(current_team_id) if current_team_id else None,
            "target_team_id": target_team_id,
        }

        if target_team_id and str(current_team_id or "") == str(target_team_id):
            summary["already_correct"] += 1
            assignment["action"] = "unchanged"
            assignments.append(assignment)
            continue

        if dry_run or not target_team_id:
            if current_team_id:
                summary["would_reassign"] += 1
                assignment["action"] = "would_reassign"
            else:
                summary["would_assign"] += 1
                assignment["action"] = "would_assign"
            assignments.append(assignment)
            continue

        assign_employee_to_team(employee_id, target_team_id, resolved_company_id)
        summary["assigned"] += 1
        assignment["action"] = "reassigned" if current_team_id else "assigned"
        assignments.append(assignment)

    summary["teams_created"] = sum(1 for t in teams.values() if t.get("created"))

    return {
        "company_id": resolved_company_id,
        "company_name": company.get("company_name"),
        "dry_run": dry_run,
        "filename": filename,
        "teams": teams,
        "summary": summary,
        "unmatched": unmatched,
        "ambiguous": ambiguous,
        "assignments": assignments,
    }
