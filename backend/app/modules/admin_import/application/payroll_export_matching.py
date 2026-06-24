"""Rapprochement salarié pour import export paie (NIR prioritaire)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.modules.admin_import.application.payroll_export_mapping import (
    normalize_nir,
    nir_match_key,
)
from app.modules.admin_import.application.rib_matching import (
    _match_by_email,
    _match_by_names,
    _match_by_payroll_matricule,
    _row_identity_fields,
    resolve_rib_row_match,
)
from app.modules.schedules.schemas.ai import RosterEmployee


def _match_by_nir(nir: str, employees: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    key = nir_match_key(nir)
    if not key or len(key) < 13:
        return None
    matches = [
        e
        for e in employees
        if nir_match_key(str(e.get("nir") or "")) == key
    ]
    return matches[0] if len(matches) == 1 else None


def _result(
    emp: Dict[str, Any],
    method: str,
    confidence: str,
    status: str,
    warnings: List[str],
) -> Dict[str, Any]:
    label = f"{emp.get('first_name', '')} {emp.get('last_name', '')}".strip()
    return {
        "employee_id": str(emp["id"]),
        "matched_name": label or None,
        "match_confidence": confidence,
        "match_method": method,
        "review_status": status,
        "warnings": warnings,
    }


def resolve_payroll_export_row_match(
    *,
    roster: List[RosterEmployee],
    employees: List[Dict[str, Any]],
    nir: str,
    matricule: str,
    email: str,
    first_name: str,
    last_name: str,
    identifiant: str = "",
) -> Dict[str, Any]:
    fn, ln, _full, identity, mat = _row_identity_fields(
        matricule=matricule or identifiant,
        email=email,
        first_name=first_name,
        last_name=last_name,
        full_name="",
    )
    warnings: List[str] = []
    nir_key = nir_match_key(nir) if nir else ""

    if nir_key and len(nir_key) >= 13:
        found = _match_by_nir(nir, employees)
        if found:
            return _result(found, "nir", "high", "ok", warnings)

    if email:
        found = _match_by_email(email, employees)
        if found:
            return _result(found, "email", "high", "ok", warnings)

    if mat or identifiant:
        found = _match_by_payroll_matricule(mat or identifiant, employees)
        if found:
            return _result(found, "matricule", "high", "ok", warnings)

    if fn and ln:
        found = _match_by_names(fn, ln, employees)
        if found:
            result = _result(found, "name_exact", "high", "ok", warnings)
            if nir_key and len(nir_key) >= 13:
                result["warnings"] = list(warnings)
            return result

    fallback = resolve_rib_row_match(
        roster=roster,
        employees=employees,
        matricule=mat or identifiant,
        email=email,
        first_name=fn,
        last_name=ln,
        full_name=identity,
    )
    if fallback.get("employee_id"):
        return fallback

    if nir_key and len(nir_key) >= 13:
        warnings.append("NIR présent dans le fichier mais aucun salarié correspondant.")

    return {
        "employee_id": None,
        "matched_name": None,
        "match_confidence": "none",
        "match_method": "none",
        "review_status": "error",
        "warnings": warnings
        + ["Employé non identifié — associez manuellement ou importez la DSN d'abord."],
    }
