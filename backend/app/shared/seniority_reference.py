"""Date de référence ancienneté (reprise / accord) — usage paie et imports."""

from __future__ import annotations

from typing import Any


def resolve_seniority_reference_date(employee: dict[str, Any] | None) -> str | None:
    """Date reprise explicite, ou repli métadonnée DSN si présente."""
    if not employee:
        return None
    raw = employee.get("seniority_reference_date")
    if raw:
        return str(raw)[:10]
    spec = employee.get("specificites_paie") or {}
    if isinstance(spec, dict):
        dsn = spec.get("dsn_anciennete") or {}
        if isinstance(dsn, dict):
            dsn_date = dsn.get("date_anciennete")
            if dsn_date:
                return str(dsn_date)[:10]
    return None


def resolve_date_anciennete_prime(employee: dict[str, Any] | None) -> str | None:
    """Date pour le calcul de la prime d'ancienneté (reprise prioritaire sur embauche)."""
    ref = resolve_seniority_reference_date(employee)
    if ref:
        return ref
    if not employee:
        return None
    hire = employee.get("hire_date") or employee.get("date_entree")
    return str(hire)[:10] if hire else None


def resolve_date_anciennete_from_contrat(contrat: dict[str, Any] | None) -> str | None:
    """Lit la date ancienneté prime depuis un contrat.json paie."""
    if not contrat or not isinstance(contrat, dict):
        return None
    block = contrat.get("contrat") or {}
    if isinstance(block, dict):
        ref = block.get("seniority_reference_date")
        if ref:
            return str(ref)[:10]
    employee_like = {
        "seniority_reference_date": block.get("seniority_reference_date")
        if isinstance(block, dict)
        else None,
        "hire_date": block.get("date_entree") if isinstance(block, dict) else None,
        "specificites_paie": contrat.get("specificites_paie"),
    }
    return resolve_date_anciennete_prime(employee_like)
