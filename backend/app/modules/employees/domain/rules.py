"""
Règles métier pures du module employees.

Aucune dépendance FastAPI, DB ou HTTP. Utilisées par l'application.
"""

from typing import Any, Dict, List

# Comportement identique au router legacy (employment_status par défaut, etc.)

DEFAULT_EMPLOYMENT_STATUS = "actif"
DEFAULT_RESIDENCE_PERMIT_SUBJECT = False


def build_employee_folder_name(
    normalized_last_name: str, normalized_first_name: str
) -> str:
    """
    Construit le nom de dossier employé à partir des noms normalisés.
    Comportement legacy : "{LAST_NAME}_{First_Name}" (ex. DUPONT_Jean).
    """
    return f"{normalized_last_name}_{normalized_first_name}"


def default_company_data_fallback() -> Dict[str, Any]:
    """Données entreprise par défaut si lecture BDD échoue (comportement legacy)."""
    return {
        "company_name": "MAJI",
        "siret": "N/A",
        "email": "contact@maji.com",
    }


__all__: List[str] = [
    "DEFAULT_EMPLOYMENT_STATUS",
    "DEFAULT_RESIDENCE_PERMIT_SUBJECT",
    "build_employee_folder_name",
    "default_company_data_fallback",
]
