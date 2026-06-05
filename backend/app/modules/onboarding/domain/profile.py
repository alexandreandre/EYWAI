"""Complétude de la fiche paie d'un nouveau salarié.

Une embauche issue du module recrutement crée une fiche minimale (état civil et
contrat de base) sans les informations indispensables à la paie. Ce module
détermine les champs encore manquants pour finaliser l'intégration.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

# Champs essentiels pour finaliser la paie d'un salarié fraîchement embauché.
# Tuple (clé colonne employees, libellé affiché côté RH).
PAYROLL_REQUIRED_FIELDS: List[Tuple[str, str]] = [
    ("nir", "Numéro de sécurité sociale"),
    ("date_naissance", "Date de naissance"),
    ("adresse", "Adresse postale"),
    ("coordonnees_bancaires", "Coordonnées bancaires (RIB)"),
    ("salaire_de_base", "Rémunération"),
]


PAYROLL_ACTIVE_STATUSES = frozenset({"actif", "active"})
DEFAULT_EMPLOYMENT_STATUS = "actif"


def _is_blank(value: Any) -> bool:
    """Considère None, chaîne vide, dict/list vides (ou entièrement vides) comme absent."""
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, dict):
        return len(value) == 0 or all(_is_blank(v) for v in value.values())
    if isinstance(value, (list, tuple, set)):
        return len(value) == 0
    return False


def missing_payroll_fields(employee: Dict[str, Any]) -> List[str]:
    """Libellés des champs paie manquants pour finaliser la fiche."""
    return [
        label
        for key, label in PAYROLL_REQUIRED_FIELDS
        if _is_blank(employee.get(key))
    ]


def is_profile_complete(employee: Dict[str, Any]) -> bool:
    return not missing_payroll_fields(employee)


def is_payroll_eligible(employee: Dict[str, Any]) -> bool:
    """Salarié actif avec fiche paie complète — éligible à la génération de bulletins."""
    status = str(employee.get("employment_status") or DEFAULT_EMPLOYMENT_STATUS).lower()
    if status not in PAYROLL_ACTIVE_STATUSES:
        return False
    return is_profile_complete(employee)


def payroll_block_reason(employee: Dict[str, Any]) -> str | None:
    """Message d'erreur si le salarié n'est pas éligible à la paie, sinon None."""
    status = str(employee.get("employment_status") or DEFAULT_EMPLOYMENT_STATUS).lower()
    missing = missing_payroll_fields(employee)
    if status == "en_onboarding":
        fields = ", ".join(missing) if missing else "informations paie"
        return (
            "La fiche de ce collaborateur est incomplète (onboarding en cours). "
            f"Complétez : {fields}."
        )
    if status not in PAYROLL_ACTIVE_STATUSES:
        return f"Ce collaborateur n'est pas actif (statut : {status})."
    if missing:
        return (
            "Impossible de générer un bulletin : fiche paie incomplète. "
            f"Manque : {', '.join(missing)}."
        )
    return None
