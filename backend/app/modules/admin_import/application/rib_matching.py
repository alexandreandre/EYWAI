"""Rapprochement salarié pour import RIB (paie : matricule = nom tronqué)."""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, List, Optional, Tuple

from app.modules.schedules.application.employee_match import resolve_employee_for_timesheet
from app.modules.schedules.schemas.ai import RosterEmployee


def _normalize(value: str) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(c for c in text if not unicodedata.combining(c))
    return " ".join(text.lower().split())


def _normalize_token(value: str) -> str:
    return _normalize(value).replace(" ", "")


def _parse_full_name(raw: str) -> Tuple[str, str]:
    """Découpe « Prénom NOM » ou « NOM Prénom » paie."""
    parts = [p for p in (raw or "").split() if p]
    if len(parts) < 2:
        return "", (parts[0] if parts else "")
    if parts[-1].isupper() and len(parts[-1]) >= 2 and not parts[0].isupper():
        return " ".join(parts[:-1]), parts[-1]
    if parts[0].isupper() and len(parts[0]) >= 2 and not parts[-1].isupper():
        return " ".join(parts[1:]), parts[0]
    return " ".join(parts[:-1]), parts[-1]


def _row_identity_fields(
    *,
    matricule: str,
    email: str,
    first_name: str,
    last_name: str,
    full_name: str,
) -> Tuple[str, str, str, str, str]:
    fn = first_name.strip()
    ln = last_name.strip()
    full = full_name.strip()

    if full and not fn and not ln:
        fn, ln = _parse_full_name(full)
    elif fn and not ln and " " in fn:
        fn, ln = _parse_full_name(fn)
    elif ln and not fn and " " in ln:
        fn, ln = _parse_full_name(ln)

    identity = f"{fn} {ln}".strip() if fn and ln else full or email or (f"Matricule {matricule}" if matricule else "")
    return fn, ln, full, identity, matricule.strip()


def _match_by_email(email: str, employees: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    target = email.strip().lower()
    if not target:
        return None
    matches = [e for e in employees if (e.get("email") or "").strip().lower() == target]
    return matches[0] if len(matches) == 1 else None


def _match_by_names(
    first_name: str,
    last_name: str,
    employees: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    fn = _normalize(first_name)
    ln = _normalize(last_name)
    if not fn or not ln:
        return None
    matches = [
        e
        for e in employees
        if _normalize(e.get("first_name") or "") == fn
        and _normalize(e.get("last_name") or "") == ln
    ]
    return matches[0] if len(matches) == 1 else None


def _match_by_payroll_matricule(
    matricule: str,
    employees: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """
    Matricule paie type Sage/Cegid : nom de famille tronqué (ex. BRISMONTIE → BRISMONTIER).
    """
    key = _normalize_token(matricule)
    if not key or key.isdigit():
        return None

    def last_key(emp: Dict[str, Any]) -> str:
        return _normalize_token(emp.get("last_name") or "")

    def folder_last_key(emp: Dict[str, Any]) -> str:
        folder = str(emp.get("employee_folder_name") or "")
        return _normalize_token(folder.split("_")[0] if "_" in folder else folder)

    exact = [e for e in employees if last_key(e) == key or folder_last_key(e) == key]
    if len(exact) == 1:
        return exact[0]

    prefix = [e for e in employees if last_key(e).startswith(key) or key.startswith(last_key(e)[: len(key)])]
    if len(prefix) == 1:
        return prefix[0]

    folder_prefix = [e for e in employees if folder_last_key(e).startswith(key)]
    if len(folder_prefix) == 1:
        return folder_prefix[0]

    return None


def _name_token_set(*parts: str) -> set[str]:
    tokens: set[str] = set()
    for part in parts:
        for token in _normalize(part).split():
            if len(token) >= 2:
                tokens.add(token)
    return tokens


def _names_compatible_with_employee(
    first_name: str,
    last_name: str,
    emp: Dict[str, Any],
    *,
    full_name: str = "",
) -> bool:
    """Même personne si les tokens du nom bulletin couvrent le dossier (ordre paie variable)."""
    payslip_tokens = _name_token_set(first_name, last_name, full_name)
    emp_tokens = _name_token_set(
        str(emp.get("first_name") or ""),
        str(emp.get("last_name") or ""),
    )
    if not payslip_tokens or not emp_tokens:
        return True
    overlap = payslip_tokens & emp_tokens
    if overlap == payslip_tokens or overlap == emp_tokens:
        return True
    return len(overlap) >= min(2, len(payslip_tokens), len(emp_tokens))


def resolve_rib_row_match(
    *,
    roster: List[RosterEmployee],
    employees: List[Dict[str, Any]],
    matricule: str,
    email: str,
    first_name: str,
    last_name: str,
    full_name: str,
    patronymic_name: str = "",
) -> Dict[str, Any]:
    fn, ln, _full, identity, mat = _row_identity_fields(
        matricule=matricule,
        email=email,
        first_name=first_name,
        last_name=last_name,
        full_name=full_name,
    )
    warnings: List[str] = []

    if email:
        found = _match_by_email(email, employees)
        if found:
            return _result(found, "email", "high", "ok", warnings)

    pat = patronymic_name.strip()
    if pat:
        patronymic_fn = fn
        if not patronymic_fn and _full:
            parsed_fn, _ = _parse_full_name(_full)
            patronymic_fn = parsed_fn
        if patronymic_fn:
            found = _match_by_names(patronymic_fn, pat, employees)
            if found:
                return _result(found, "patronymic", "high", "ok", warnings)
        found = _match_by_payroll_matricule(pat, employees)
        if found:
            return _result(found, "patronymic_matricule", "high", "ok", warnings)

    if mat:
        found = _match_by_payroll_matricule(mat, employees)
        if found:
            label = f"{found.get('first_name', '')} {found.get('last_name', '')}".strip()
            if fn and ln and _normalize(label) != _normalize(f"{fn} {ln}"):
                if _names_compatible_with_employee(fn, ln, found, full_name=_full):
                    return _result(found, "matricule", "high", "ok", warnings)
                warnings.append(
                    f"Matricule paie « {mat} » → {label} (vérifiez le prénom dans le fichier)."
                )
                return _result(found, "matricule", "medium", "warning", warnings)
            return _result(found, "matricule", "high", "ok", warnings)

    if fn and ln:
        found = _match_by_names(fn, ln, employees)
        if found:
            return _result(found, "name_exact", "high", "ok", warnings)

    proposal = resolve_employee_for_timesheet(
        raw_name=identity,
        matricule=mat or None,
        roster=roster,
    )
    if proposal.employee_id:
        return {
            "employee_id": proposal.employee_id,
            "matched_name": proposal.matched_name,
            "match_confidence": proposal.match_confidence or "none",
            "match_method": proposal.match_method or "none",
            "review_status": proposal.review_status or "error",
            "warnings": warnings + list(proposal.warnings),
        }

    warnings.append(f"Aucun salarié trouvé pour « {identity} ».")
    return {
        "employee_id": None,
        "matched_name": None,
        "match_confidence": "none",
        "match_method": "none",
        "review_status": "error",
        "warnings": warnings,
    }


def _result(
    emp: Dict[str, Any],
    method: str,
    confidence: str,
    status: str,
    warnings: List[str],
) -> Dict[str, Any]:
    return {
        "employee_id": str(emp["id"]),
        "matched_name": f"{emp.get('first_name', '')} {emp.get('last_name', '')}".strip(),
        "match_confidence": confidence,
        "match_method": method,
        "review_status": status,
        "warnings": warnings,
    }
