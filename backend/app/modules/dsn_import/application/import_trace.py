"""Diagnostic de rapprochement salarié DSN ↔ fiche existante."""

from __future__ import annotations

from typing import Any, Dict, Optional

from app.modules.dsn_import.infrastructure import repository as repo


def diagnose_employee_match(
    company_id: Optional[str],
    nir: Optional[str],
    source_ref: str,
    payload: Dict[str, Any],
    employee_by_ref: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Repère comment un salarié DSN est (ou non) rattaché à une fiche existante."""
    cache = employee_by_ref or {}
    out: Dict[str, Any] = {
        "match": "none",
        "existing_id": None,
        "existing_company_id": None,
        "existing_email": None,
        "existing_user_id": None,
        "existing_employment_status": None,
        "note": None,
    }

    def _fill(emp: Dict[str, Any], match: str) -> Dict[str, Any]:
        out["match"] = match
        out["existing_id"] = str(emp.get("id") or "")
        out["existing_company_id"] = str(emp.get("company_id") or "")
        out["existing_email"] = emp.get("email")
        out["existing_user_id"] = emp.get("user_id")
        out["existing_employment_status"] = emp.get("employment_status")
        return out

    if company_id and nir:
        emp = repo.find_employee_by_nir(company_id, nir)
        if emp:
            return _fill(emp, "by_nir_company")

    if nir:
        emp = repo.find_employee_by_nir_global(nir)
        if emp:
            return _fill(emp, "by_nir_global")

    parts = source_ref.split(":")
    siret = parts[1] if len(parts) > 1 else payload.get("siret", "")
    emp_key = payload.get("employee_key") or nir
    if siret and emp_key:
        cached = cache.get(f"emp:{siret}:{emp_key}")
        if cached:
            return _fill(cached, "by_batch_cache")

    if not nir:
        out["note"] = "no_nir_in_dsn"
    else:
        out["note"] = "nir_not_in_db"
    return out
