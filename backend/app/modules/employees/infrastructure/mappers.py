"""
Mappers entre données applicatives et format persistance (employees, profiles).

Comportement identique au router legacy (dates en isoformat, défauts).
"""
from datetime import date
from typing import Any, Dict, List


def to_employee_dict(row: Dict[str, Any]) -> Dict[str, Any]:
    """Row Supabase -> dict employé (copie)."""
    return dict(row)


def prepare_employee_insert_data(
    employee_data: Dict[str, Any],
    new_user_id: str,
    company_id: str,
    username: str,
    folder_name: str,
) -> Dict[str, Any]:
    """
    Prépare le dict pour insertion dans la table employees.
    - Ajoute id, employee_folder_name, company_id, username.
    - Sérialise les dates en isoformat.
    - Défaut is_subject_to_residence_permit à False si None.
    Comportement identique au router legacy.
    """
    data = dict(employee_data)
    data["id"] = str(new_user_id)
    data["employee_folder_name"] = folder_name
    data["company_id"] = company_id
    data["username"] = username

    for date_key in ("date_naissance", "hire_date", "residence_permit_expiry_date"):
        val = data.get(date_key)
        if isinstance(val, date):
            data[date_key] = val.isoformat()

    if data.get("is_subject_to_residence_permit") is None:
        data["is_subject_to_residence_permit"] = False

    return data


__all__: List[str] = [
    "to_employee_dict",
    "prepare_employee_insert_data",
]
