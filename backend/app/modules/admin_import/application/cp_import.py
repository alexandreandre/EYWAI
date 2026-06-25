"""Cas d'usage import soldes CP depuis bulletins PDF."""

from __future__ import annotations

import unicodedata
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

from app.modules.absences.application.leave_settings_commands import (
    apply_cp_solde_import,
    bulletin_reference_date,
)
from app.modules.absences.domain.leave_policy import EmployeeLeaveAdjustment
from app.modules.absences.domain.rules import compute_cp_period_balances
from app.modules.absences.infrastructure.leave_settings_repository import (
    get_adjustments_by_employees_year,
    get_leave_policy,
)
from app.modules.absences.infrastructure.queries import get_employee_hire_date
from app.modules.absences.infrastructure.repository import absence_repository
from app.modules.admin_import.application.cp_payslip_parser import (
    ParsedPayslipPage,
    parse_pdf_file,
)
from app.modules.admin_import.application.rib_import import _build_roster
from app.modules.admin_import.application.rib_matching import (
    _parse_full_name,
    resolve_rib_row_match,
)
from app.modules.admin_import.infrastructure import repository as repo
from app.modules.admin_import.schemas.requests import CpImportCommitBody

MAX_FILES = 1000
MAX_TOTAL_BYTES = 200 * 1024 * 1024


def _normalize_token(value: str) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(c for c in text if not unicodedata.combining(c))
    return text.lower().replace(" ", "")


def _dedupe_key(page: ParsedPayslipPage) -> Optional[Tuple[str, str, int, int]]:
    if not page.siret or not page.matricule or not page.year or not page.month:
        return None
    return (
        page.siret,
        _normalize_token(page.matricule),
        page.year,
        page.month,
    )


def _dedupe_pages(pages: List[ParsedPayslipPage]) -> tuple[List[ParsedPayslipPage], int, List[str]]:
    seen: dict[Tuple[str, str, int, int], ParsedPayslipPage] = {}
    without_key: List[ParsedPayslipPage] = []
    conflicts: List[str] = []
    duplicates_removed = 0

    for page in pages:
        key = _dedupe_key(page)
        if not key:
            without_key.append(page)
            continue
        if key not in seen:
            seen[key] = page
            continue
        duplicates_removed += 1
        prev = seen[key]
        if (
            prev.cp_n1_solde != page.cp_n1_solde
            or prev.cp_n_solde != page.cp_n_solde
        ):
            conflicts.append(
                f"{page.source_file} p.{page.page_index} : soldes CP différents pour "
                f"{page.matricule} ({prev.cp_n1_solde}/{prev.cp_n_solde} vs "
                f"{page.cp_n1_solde}/{page.cp_n_solde})."
            )

    return list(seen.values()) + without_key, duplicates_removed, conflicts


def _compute_current_cp_soldes(
    employee_id: str,
    company_id: str,
    year: int,
    month: Optional[int] = None,
) -> tuple[Optional[float], Optional[float]]:
    hire_raw = get_employee_hire_date(employee_id)
    if not hire_raw:
        return None, None
    hire_date = (
        date.fromisoformat(hire_raw)
        if isinstance(hire_raw, str)
        else hire_raw
    )
    policy = get_leave_policy(company_id)
    adjustments = get_adjustments_by_employees_year([employee_id], year)
    adjustment = adjustments.get(employee_id, EmployeeLeaveAdjustment.empty())
    validated = absence_repository.list_validated_for_employees([employee_id])
    ref = bulletin_reference_date(year, month)
    periods = compute_cp_period_balances(
        hire_date,
        validated,
        ref,
        policy=policy,
        adjustment=adjustment,
    )
    return float(periods["n1_remaining"]), float(periods["n_remaining"])


def _flag_duplicate_employee_matches(previews: List[Dict[str, Any]]) -> int:
    """Marque en erreur les lignes partageant le même salarié rapproché."""
    by_employee: Dict[str, List[int]] = {}
    for item in previews:
        emp_id = item.get("employee_id")
        if not emp_id:
            continue
        by_employee.setdefault(str(emp_id), []).append(int(item["row_index"]))

    conflict_count = 0
    for emp_id, row_indices in by_employee.items():
        if len(row_indices) <= 1:
            continue
        conflict_count += 1
        label = ", ".join(str(i) for i in sorted(row_indices))
        warning = (
            f"Plusieurs bulletins rapprochés au même salarié "
            f"(lignes {label}) — un seul solde CP par personne."
        )
        for item in previews:
            if str(item.get("employee_id")) != emp_id:
                continue
            item["review_status"] = "error"
            item["duplicate_employee_conflict"] = True
            if warning not in item["warnings"]:
                item["warnings"].append(warning)
    return conflict_count


def parse_cp_import_files(
    files: List[Tuple[str, bytes]],
) -> Dict[str, Any]:
    if len(files) > MAX_FILES:
        raise ValueError(f"Maximum {MAX_FILES} fichiers par import.")
    total_size = sum(len(content) for _, content in files)
    if total_size > MAX_TOTAL_BYTES:
        raise ValueError("Taille totale des fichiers trop importante (max 200 Mo).")

    all_pages: List[ParsedPayslipPage] = []
    file_errors: List[str] = []
    files_processed = 0
    files_failed = 0

    for filename, content in files:
        if not filename.lower().endswith(".pdf"):
            file_errors.append(f"{filename} : format non supporté (PDF attendu).")
            files_failed += 1
            continue
        if not content:
            file_errors.append(f"{filename} : fichier vide.")
            files_failed += 1
            continue
        try:
            pages, warnings = parse_pdf_file(filename, content)
            for w in warnings:
                file_errors.append(f"{filename} : {w}")
            if pages:
                all_pages.extend(pages)
                files_processed += 1
            else:
                files_failed += 1
        except Exception as exc:
            file_errors.append(f"{filename} : {exc}")
            files_failed += 1

    deduped, duplicates_removed, conflicts = _dedupe_pages(all_pages)
    file_errors.extend(conflicts)

    companies_by_page_key: Dict[str, Dict[str, Any]] = {}
    company_resolution_warnings: Dict[str, List[str]] = {}
    seen_page_keys: set[str] = set()
    for page in deduped:
        page_key = f"{page.siret or ''}|{page.company_name or ''}"
        if page_key in seen_page_keys:
            continue
        seen_page_keys.add(page_key)
        company, resolve_warnings = repo.resolve_company_from_payslip(
            page.siret, page.company_name
        )
        if company:
            companies_by_page_key[page_key] = company
        if resolve_warnings:
            company_resolution_warnings[page_key] = resolve_warnings

    company_ids = [str(c["id"]) for c in companies_by_page_key.values()]
    employees_by_company = repo.list_employees_by_company_ids(company_ids)
    rosters_by_company: Dict[str, List[Dict[str, Any]]] = {}

    previews: List[Dict[str, Any]] = []
    summary = {
        "total": 0,
        "ready": 0,
        "warning": 0,
        "error": 0,
        "files_processed": files_processed,
        "files_failed": files_failed,
        "duplicates_removed": duplicates_removed,
    }

    matched_employee_ids: List[str] = []
    row_years: Dict[str, int] = {}

    for idx, page in enumerate(deduped, start=1):
        warnings: List[str] = list(page.parse_errors)
        if page.repos_cadre_days:
            warnings.append(
                f"Solde repos cadre ({page.repos_cadre_days} j) détecté — non importé en v1."
            )

        company_id: Optional[str] = None
        company_name: Optional[str] = page.company_name
        review_status = "error"

        page_key = f"{page.siret or ''}|{page.company_name or ''}"
        co = companies_by_page_key.get(page_key)
        if co:
            company_id = str(co["id"])
            company_name = co.get("company_name") or company_name
        warnings.extend(company_resolution_warnings.get(page_key, []))

        first_name, last_name = "", ""
        if page.raw_name:
            first_name, last_name = _parse_full_name(page.raw_name)

        match: Dict[str, Any] = {
            "employee_id": None,
            "matched_name": None,
            "match_confidence": "none",
            "match_method": "none",
            "review_status": "error",
            "warnings": [],
        }

        if company_id:
            employees = employees_by_company.get(company_id, [])
            roster = _build_roster(employees)
            rosters_by_company[company_id] = [
                {
                    "id": str(e["id"]),
                    "first_name": str(e.get("first_name") or ""),
                    "last_name": str(e.get("last_name") or ""),
                    "time_tracking_id": e.get("time_tracking_id"),
                }
                for e in employees
            ]
            match = resolve_rib_row_match(
                roster=roster,
                employees=employees,
                matricule=page.matricule or "",
                email="",
                first_name=first_name,
                last_name=last_name,
                full_name=page.raw_name or "",
                patronymic_name=page.patronymic_name or "",
                strict_matricule_fallback=True,
            )
            review_status = match.get("review_status") or "error"
            warnings.extend(match.get("warnings") or [])

        if page.cp_n1_solde is None or page.cp_n_solde is None:
            review_status = "error"
            if not any("CP" in w for w in warnings):
                warnings.append("Soldes CP non extraits.")

        year = page.year or date.today().year
        identity = page.raw_name or page.matricule or f"Ligne {idx}"
        if page.patronymic_name:
            identity = f"{identity} (pat. {page.patronymic_name})"

        item: Dict[str, Any] = {
            "row_index": idx,
            "source_file": page.source_file,
            "page_index": page.page_index,
            "company_id": company_id,
            "company_name": company_name,
            "siret": page.siret,
            "period_label": page.period_label,
            "year": year,
            "month": page.month,
            "raw_identity": identity,
            "matricule": page.matricule,
            "cp_n1_solde": page.cp_n1_solde if page.cp_n1_solde is not None else 0.0,
            "cp_n_solde": page.cp_n_solde if page.cp_n_solde is not None else 0.0,
            "acquis_n1": page.acquis_n1,
            "acquis_n": page.acquis_n,
            "pris_n1": page.pris_n1,
            "pris_n": page.pris_n,
            "employee_id": match.get("employee_id"),
            "matched_name": match.get("matched_name"),
            "match_confidence": match.get("match_confidence") or "none",
            "match_method": match.get("match_method") or "none",
            "review_status": review_status,
            "warnings": warnings,
            "parse_format": page.parse_format,
            "current_cp_n1": None,
            "current_cp_n": None,
            "delta_cp_n1": None,
            "delta_cp_n": None,
            "has_existing_adjustment": False,
        }

        emp_id = match.get("employee_id")
        if emp_id and company_id:
            matched_employee_ids.append(str(emp_id))
            row_years[str(emp_id)] = year

        previews.append(item)
        summary["total"] += 1
        if review_status == "ok":
            summary["ready"] += 1
        elif review_status == "warning":
            summary["warning"] += 1
        else:
            summary["error"] += 1

    duplicate_conflicts = _flag_duplicate_employee_matches(previews)
    if duplicate_conflicts:
        summary["duplicate_conflicts"] = duplicate_conflicts
        summary["ready"] = sum(1 for item in previews if item["review_status"] == "ok")
        summary["warning"] = sum(1 for item in previews if item["review_status"] == "warning")
        summary["error"] = sum(1 for item in previews if item["review_status"] == "error")

    if matched_employee_ids:
        years = set(row_years.values())
        adjustments_by_year: Dict[int, Dict[str, EmployeeLeaveAdjustment]] = {}
        for y in years:
            adjustments_by_year[y] = get_adjustments_by_employees_year(
                list(set(
                    eid for eid, yr in row_years.items() if yr == y
                )),
                y,
            )

        for item in previews:
            emp_id = item.get("employee_id")
            company_id = item.get("company_id")
            year = item.get("year")
            if not emp_id or not company_id or not year:
                continue
            adj = adjustments_by_year.get(year, {}).get(str(emp_id))
            if adj and (
                adj.cp_n1_opening_balance != 0
                or adj.cp_n_opening_balance != 0
                or adj.rtt_opening_balance != 0
            ):
                item["has_existing_adjustment"] = True
            current_n1, current_n = _compute_current_cp_soldes(
                str(emp_id),
                str(company_id),
                int(year),
                item.get("month"),
            )
            item["current_cp_n1"] = current_n1
            item["current_cp_n"] = current_n
            if current_n1 is not None:
                item["delta_cp_n1"] = round(item["cp_n1_solde"] - current_n1, 2)
            if current_n is not None:
                item["delta_cp_n"] = round(item["cp_n_solde"] - current_n, 2)

    return {
        "rows": previews,
        "rosters_by_company": rosters_by_company,
        "summary": summary,
        "file_errors": file_errors,
    }


def commit_cp_import(body: CpImportCommitBody) -> Dict[str, Any]:
    applied = 0
    skipped = 0
    results: List[Dict[str, Any]] = []
    errors: List[str] = []

    employees_cache: Dict[str, set[str]] = {}
    seen_employee_year: set[tuple[str, str, int]] = set()

    for row in body.rows:
        if not row.confirmed:
            skipped += 1
            continue

        if row.company_id not in employees_cache:
            employees = repo.list_company_employees(row.company_id)
            employees_cache[row.company_id] = {str(e["id"]) for e in employees}

        if row.employee_id not in employees_cache[row.company_id]:
            skipped += 1
            errors.append(
                f"Ligne {row.row_index} : employé hors entreprise."
            )
            continue

        dedupe_key = (row.company_id, row.employee_id, row.year)
        if dedupe_key in seen_employee_year:
            skipped += 1
            errors.append(
                f"Ligne {row.row_index} : plusieurs bulletins pour le même salarié "
                f"et la même année — un seul enregistrement autorisé."
            )
            continue
        seen_employee_year.add(dedupe_key)

        note = None
        if row.period_label and row.source_file:
            note = f"Import CP bulletin {row.period_label} ({row.source_file})"
        elif row.source_file:
            note = f"Import CP bulletin ({row.source_file})"

        try:
            apply_cp_solde_import(
                row.company_id,
                row.employee_id,
                row.year,
                cp_n1_solde=row.cp_n1_solde,
                cp_n_solde=row.cp_n_solde,
                month=row.month,
                note=note,
            )
            results.append(
                {
                    "row_index": row.row_index,
                    "employee_id": row.employee_id,
                    "success": True,
                    "message": "Soldes CP enregistrés.",
                    "duplicate_warnings": [],
                }
            )
            applied += 1
        except Exception as exc:
            skipped += 1
            msg = str(exc)
            errors.append(f"Ligne {row.row_index} : {msg}")
            results.append(
                {
                    "row_index": row.row_index,
                    "employee_id": row.employee_id,
                    "success": False,
                    "message": msg,
                    "duplicate_warnings": [],
                }
            )

    return {
        "applied": applied,
        "skipped": skipped,
        "results": results,
        "errors": errors,
    }
