# Cas d'usage en lecture du module auth.
# Utilise uniquement infrastructure (IResetTokenStore). Comportement identique au legacy.

from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException

from app.modules.auth.application.dto import VerifyResetTokenResult
from app.modules.auth.infrastructure import reset_token_repository


def verify_reset_token(token: str) -> VerifyResetTokenResult:
    """
    Vérifie si un token de réinitialisation est valide et non expiré (IResetTokenStore).
    Lève HTTPException(400) si token invalide ou expiré.
    """
    try:
        print(f"🔍 [PASSWORD RESET] Vérification du token: {token[:10]}...")

        token_data = reset_token_repository.get_valid(token)
        if not token_data:
            print("❌ [PASSWORD RESET] Token non trouvé ou déjà utilisé")
            raise HTTPException(status_code=400, detail="Token invalide")

        expires_at = datetime.fromisoformat(
            token_data["expires_at"].replace("Z", "+00:00")
        )
        if datetime.now(expires_at.tzinfo) > expires_at:
            print("❌ [PASSWORD RESET] Token expiré")
            raise HTTPException(status_code=400, detail="Token expiré")

        print("✅ [PASSWORD RESET] Token valide")
        return VerifyResetTokenResult(valid=True, email=token_data["email"])

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ [PASSWORD RESET] Erreur: {e}")
        raise HTTPException(status_code=400, detail="Token invalide")


def get_me(current_user: object) -> object:
    """Retourne l'utilisateur connecté (contexte fourni par le router)."""
    return current_user
