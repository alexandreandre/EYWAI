"""
Exceptions applicatives du module schedules.

Utilisées par commands/queries ; le router (lors de la migration) les convertira en HTTPException.
"""


class ScheduleAppError(Exception):
    """Erreur applicative schedules (à mapper en 400/404/500 par le router)."""
    def __init__(self, code: str, message: str, status_code: int = 500):
        self.code = code  # not_found, validation, bad_request
        self.message = message
        self.status_code = status_code
        super().__init__(message)
