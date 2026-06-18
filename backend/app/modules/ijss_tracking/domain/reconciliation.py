"""Règles de rapprochement IJSS (pur domaine, sans I/O)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class MatchCandidate:
    employee_id: str
    confidence: str
    reason: str


def normalize_name(value: str) -> str:
    return " ".join((value or "").upper().split())


def normalize_nir(value: str) -> str:
    return "".join(c for c in (value or "") if c.isdigit())[:15]


def amounts_close(a: float, b: float, tolerance: float) -> bool:
    return abs(float(a) - float(b)) <= tolerance


def match_received_to_employee(
    *,
    employee_name_raw: str,
    employee_nir: Optional[str],
    amount: float,
    employees: List[Dict[str, Any]],
    expected_lines: List[Dict[str, Any]],
    tolerance_strong: float = 0.01,
    tolerance_medium: float = 2.0,
) -> Optional[MatchCandidate]:
    """Propose un rapprochement salarié pour une ligne reçue."""
    nir_clean = normalize_nir(employee_nir or "")
    name_clean = normalize_name(employee_name_raw)

    by_id = {str(e["id"]): e for e in employees}

    if nir_clean:
        for emp in employees:
            emp_nir = normalize_nir(str(emp.get("nir") or ""))
            if emp_nir and emp_nir == nir_clean:
                return MatchCandidate(
                    employee_id=str(emp["id"]),
                    confidence="strong",
                    reason="NIR identique",
                )

    if name_clean:
        for emp in employees:
            full = normalize_name(
                f"{emp.get('last_name', '')} {emp.get('first_name', '')}"
            )
            if full and (full in name_clean or name_clean in full):
                return MatchCandidate(
                    employee_id=str(emp["id"]),
                    confidence="medium",
                    reason="Nom salarié reconnu",
                )

    for line in expected_lines:
        emp = by_id.get(str(line.get("employee_id") or ""))
        if not emp:
            continue
        expected_amt = float(line.get("ijss_subrogees_bulletin") or line.get("ijss_theorique") or 0)
        if expected_amt > 0 and amounts_close(expected_amt, amount, tolerance_strong):
            return MatchCandidate(
                employee_id=str(emp["id"]),
                confidence="strong",
                reason="Montant = IJSS bulletin attendu",
            )

    for line in expected_lines:
        emp = by_id.get(str(line.get("employee_id") or ""))
        if not emp:
            continue
        expected_amt = float(line.get("ijss_subrogees_bulletin") or line.get("ijss_theorique") or 0)
        if expected_amt > 0 and amounts_close(expected_amt, amount, tolerance_medium):
            return MatchCandidate(
                employee_id=str(emp["id"]),
                confidence="weak",
                reason="Montant proche de l'attendu",
            )

    return None


def aggregate_line_status(
    *,
    expected_amount: float,
    cpam_amount: float,
    bank_amount: float,
    threshold: float,
    has_justification: bool,
) -> str:
    """Statut d'une ligne attendue."""
    if expected_amount <= 0:
        return "pending"
    cpam_ok = cpam_amount > 0 and amounts_close(expected_amount, cpam_amount, threshold)
    bank_ok = bank_amount > 0 and amounts_close(expected_amount, bank_amount, threshold)
    if cpam_ok and bank_ok:
        return "ok"
    if has_justification:
        return "justified"
    if cpam_amount > 0 or bank_amount > 0:
        return "variance" if not (cpam_ok or bank_ok) else "partial"
    return "pending"


def aggregate_period_status(line_statuses: List[str]) -> str:
    if not line_statuses:
        return "open"
    if all(s in ("ok", "justified") for s in line_statuses):
        return "reconciled"
    if any(s in ("variance", "partial") for s in line_statuses):
        return "partial"
    if any(s == "pending" for s in line_statuses):
        return "open"
    return "partial"
