"""
DTOs et exceptions du module employee_exits.

Exception levée par la couche application ; le router (API) peut la convertir en HTTPException.
Réexport des builders/mappers depuis infrastructure pour les commands (build_exit_record, constantes).
build_document_data_from_exit est importé depuis infrastructure.mappers dans queries.
Aucune dépendance FastAPI dans ce fichier.
"""
from app.modules.employee_exits.infrastructure.mappers import (
    DOCUMENT_NAME_MAP,
    GENERATABLE_DOCUMENT_TYPES,
    build_exit_record,
)


class EmployeeExitApplicationError(Exception):
    """Erreur métier ou validation ; à mapper vers HTTPException par l'API."""

    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


# Réexport pour les commands (build_exit_record, constantes)
__all__ = [
    "EmployeeExitApplicationError",
    "build_exit_record",
    "DOCUMENT_NAME_MAP",
    "GENERATABLE_DOCUMENT_TYPES",
]
