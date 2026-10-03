"""
Exceptions applicatives du module schedules.

Utilisées par commands/queries ; le router (lors de la migration) les convertira en HTTPException.
"""


from typing import Any, Optional


class ScheduleAppError(Exception):
    """Erreur applicative schedules (à mapper en 400/404/500 par le router).

    `detail` : corps structuré renvoyé tel quel au front quand l'écran doit
    proposer une suite (ex. « Refaire l'import de ce fichier ») ; il porte
    toujours `message`. Sans lui, le front reçoit la phrase seule.
    """

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 500,
        detail: Optional[dict[str, Any]] = None,
    ):
        self.code = code  # not_found, validation, bad_request
        self.message = message
        self.status_code = status_code
        self.detail = detail
        super().__init__(message)
