"""
Règles métier pures du domaine company_groups.

Aucune dépendance FastAPI ni DB. Validation et règles sur les données uniquement.
Comportement aligné sur les attentes des routeurs (group_name requis, siren optionnel 9 caractères).
"""
from __future__ import annotations

import re
from typing import Any, Dict, Optional


# SIREN : 9 chiffres (optionnel)
SIREN_PATTERN = re.compile(r"^\d{9}$")


def validate_group_name(group_name: Optional[str]) -> bool:
    """Vérifie que le nom du groupe est non vide (après strip)."""
    if group_name is None:
        return False
    return bool(str(group_name).strip())


def validate_siren(siren: Optional[str]) -> bool:
    """Vérifie le format SIREN si renseigné (9 chiffres)."""
    if siren is None or str(siren).strip() == "":
        return True
    return bool(SIREN_PATTERN.match(str(siren).strip()))


def validate_group_create_data(data: Dict[str, Any]) -> None:
    """
    Valide les données de création/mise à jour d'un groupe.
    Lève ValueError si invalide. Règles : group_name non vide, siren format optionnel.
    """
    if not validate_group_name(data.get("group_name")):
        raise ValueError("group_name est requis et ne peut pas être vide")
    if not validate_siren(data.get("siren")):
        raise ValueError("siren doit contenir exactement 9 chiffres si renseigné")


def validate_metric_for_comparison(metric: str) -> bool:
    """Vérifie que la métrique de comparaison est autorisée (employees, payroll, absences)."""
    return metric in ("employees", "payroll", "absences")
