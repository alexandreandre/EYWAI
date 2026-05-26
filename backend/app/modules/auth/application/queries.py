# Cas d'usage en lecture du module auth.
# Utilise uniquement infrastructure (IResetTokenStore). Comportement identique au legacy.

from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException

from app.core.logging import get_logger
from app.modules.auth.application.dto import VerifyResetTokenResult
from app.modules.auth.infrastructure import reset_token_repository

logger = get_logger("modules.auth")


def verify_reset_token(token: str) -> VerifyResetTokenResult:
    """
    Vérifie si un token de réinitialisation est valide et non expiré (IResetTokenStore).
    Lève HTTPException(400) si token invalide ou expiré.
    """
    try:
        token_data = reset_token_repository.get_valid(token)
        if not token_data:
            raise HTTPException(status_code=400, detail="Token invalide")

        expires_at = datetime.fromisoformat(
            token_data["expires_at"].replace("Z", "+00:00")
        )
        if datetime.now(expires_at.tzinfo) > expires_at:
            raise HTTPException(status_code=400, detail="Token expiré")

        return VerifyResetTokenResult(valid=True, email=token_data["email"])

    except HTTPException:
        raise
    except Exception as e:

        logger.warning("Vérification token reset: %s", e)
        raise HTTPException(status_code=400, detail="Token invalide")


def get_me(current_user: object) -> object:
    """Retourne l'utilisateur connecté (contexte fourni par le router)."""
    return current_user
