"""
DTOs et exceptions applicatives du module employees.
"""
from typing import Any, Dict, List


class EmployeeCreateValidationError(Exception):
    """
    Levée lorsque la création d'un employé échoue pour cause de contraintes
    (ex. email ou NIR déjà utilisés). Permet au router de renvoyer une réponse
    400 avec field_errors (comportement identique au router legacy).
    """

    def __init__(self, field_errors: Dict[str, str], message: str = "Erreur lors de la création de l'employé"):
        self.field_errors = field_errors
        self.message = message
        super().__init__(message)


__all__: List[str] = ["EmployeeCreateValidationError"]
