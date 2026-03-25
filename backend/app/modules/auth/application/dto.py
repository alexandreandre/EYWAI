# DTOs applicatifs du module auth (résultats internes, pas contrats HTTP).

from pydantic import BaseModel


class VerifyResetTokenResult(BaseModel):
    """Résultat de la vérification d'un token de réinitialisation."""

    valid: bool
    email: str | None = None
