"""Règles de sélection mutuelle par un salarié."""

from __future__ import annotations

from typing import Any


def _normalize_statut(statut: str | None) -> str:
    compact = (statut or "").strip().lower().replace(" ", "").replace("-", "")
    if "cadre" in compact and "noncadre" not in compact:
        return "cadre"
    return "non_cadre"


def is_mutuelle_eligible_for_employee(
    mutuelle: dict[str, Any],
    employee_statut: str | None,
) -> bool:
    """Formule active et compatible avec le statut du salarié."""
    if not mutuelle.get("is_active", True):
        return False
    cat = mutuelle.get("statut_categoriel") or "tous"
    if cat == "tous":
        return True
    return cat == _normalize_statut(employee_statut)


def resolve_organisme_label(
    mutuelle: dict[str, Any] | None,
    company_organisme_label: str | None,
) -> str | None:
    """Libellé organisme : formule > entreprise."""
    if mutuelle:
        formula_label = (mutuelle.get("organisme_label") or "").strip()
        if formula_label:
            return formula_label
    company_label = (company_organisme_label or "").strip()
    return company_label or None
