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


#: Clé du bloc `contrat` du bulletin : jours d'ancienneté que le congé parental
#: d'éducation à temps plein ne donne pas (C. trav. L1225-54, pour moitié).
CLE_JOURS_NEUTRALISES = "jours_anciennete_neutralises"


def jours_neutralises_du_contrat(contrat: dict[str, Any] | None) -> int:
    block = (contrat or {}).get("contrat") if isinstance(contrat, dict) else None
    try:
        return max(0, int((block or {}).get(CLE_JOURS_NEUTRALISES) or 0))
    except (TypeError, ValueError):
        return 0


def decaler_selon_le_contrat(valeur: Any, contrat: dict[str, Any] | None) -> Any:
    """La date d'ancienneté (date ou ISO) repoussée des jours de congé parental
    que la loi ne compte pas ; inchangée sans congé parental."""
    jours = jours_neutralises_du_contrat(contrat)
    if not jours or not valeur:
        return valeur
    from datetime import date, timedelta

    if isinstance(valeur, date):
        return valeur + timedelta(days=jours)
    try:
        return (date.fromisoformat(str(valeur)[:10]) + timedelta(days=jours)).isoformat()
    except ValueError:
        return valeur


def depart_de_l_anciennete(employee: dict[str, Any] | None):
    """Le plus ancien de l'embauche et de la date d'ancienneté de la fiche : un
    congé parental d'avant ne retire rien à l'ancienneté (L1225-54)."""
    from datetime import date

    if not employee:
        return None
    dates = []
    for valeur in (employee.get("hire_date"), resolve_seniority_reference_date(employee)):
        try:
            dates.append(date.fromisoformat(str(valeur)[:10]))
        except ValueError:
            continue
    return min(dates) if dates else None


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
