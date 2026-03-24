"""
Providers rib_alerts : callbacks utilisés par le module employees (normalize_iban, on_rib_updated, on_rib_submitted).

Implémentation autonome dans le module : app.shared.utils.iban + repository + queries.
Aucune dépendance vers app.shared.infrastructure.rib_alert ni services/*.
Comportement strictement identique au legacy.
"""
from __future__ import annotations

from typing import Any, Dict, List

from app.modules.rib_alerts.infrastructure.queries import get_duplicate_iban_employees
from app.modules.rib_alerts.infrastructure.repository import get_rib_alert_repository
from app.shared.utils.iban import mask_iban, normalize_iban  # normalize_iban exposé comme API du module


def on_rib_updated(
    company_id: str,
    employee_id: str,
    old_iban: str,
    new_iban: str,
    employee_name: str,
) -> None:
    """
    Appelé quand le RIB d'un employé est modifié.
    Crée une alerte 'rib_modified' si l'IBAN a réellement changé (après normalisation).
    """
    old_n = normalize_iban(old_iban)
    new_n = normalize_iban(new_iban)
    if not new_n or old_n == new_n:
        return
    payload = {
        "company_id": company_id,
        "alert_type": "rib_modified",
        "title": "Modification du RIB",
        "message": f"Le RIB de {employee_name} a été modifié.",
        "details": {
            "old_iban_masked": mask_iban(old_iban) if old_iban else None,
            "new_iban_masked": mask_iban(new_iban),
        },
        "severity": "warning",
        "is_read": False,
        "is_resolved": False,
        "employee_id": employee_id,
    }
    get_rib_alert_repository().create(payload)


def on_rib_submitted(
    company_id: str,
    employee_id: str,
    new_iban: str,
    employee_name: str,
) -> List[Dict[str, Any]]:
    """
    Vérifie les doublons d'IBAN après soumission (création ou mise à jour).
    Crée une alerte 'rib_duplicate' si un autre employé a le même IBAN.
    Retourne la liste des employés en doublon (pour que le routeur puisse renvoyer un warning ou 409).
    """
    iban_n = normalize_iban(new_iban)
    if not iban_n:
        return []
    duplicates = get_duplicate_iban_employees(company_id, iban_n, exclude_employee_id=employee_id)
    if not duplicates:
        return []
    duplicate_names = [f"{d.get('first_name', '')} {d.get('last_name', '')}".strip() for d in duplicates]
    payload = {
        "company_id": company_id,
        "alert_type": "rib_duplicate",
        "title": "RIB en doublon",
        "message": f"Le RIB de {employee_name} est identique à celui d'un ou plusieurs autres employés : {', '.join(duplicate_names)}.",
        "details": {
            "iban_masked": mask_iban(new_iban),
            "duplicate_employees": duplicates,
        },
        "severity": "warning",
        "is_read": False,
        "is_resolved": False,
        "employee_id": employee_id,
    }
    get_rib_alert_repository().create(payload)
    return duplicates
