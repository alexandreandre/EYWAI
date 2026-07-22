# Cas d'usage en écriture du module auth.
# Utilise uniquement domain (règles) + infrastructure (ports, queries). Comportement identique au legacy.

from __future__ import annotations

import secrets
from datetime import datetime, timezone, timedelta

from fastapi import HTTPException

from app.core.logging import get_logger, is_app_debug_enabled
from app.modules.auth.domain.rules import RESET_TOKEN_VALIDITY_HOURS
from app.modules.auth.infrastructure import (
    auth_provider,
    email_sender,
    reset_token_repository,
)
from app.modules.auth.infrastructure.queries import (
    get_profile_display_name,
    set_must_change_password,
)

logger = get_logger("modules.auth")


def _reset_password_client_error(exc: BaseException) -> HTTPException | None:
    """Erreurs Supabase / Auth attendues sur un token invalide → 400 uniforme."""
    if type(exc).__name__ in ("APIError", "AuthApiError"):
        return HTTPException(status_code=400, detail="Token invalide ou expiré")

    lowered = str(exc).lower()
    if "403" in lowered or "forbidden" in lowered:
        return HTTPException(status_code=400, detail="Token invalide ou expiré")
    return None


def request_password_reset(email: str) -> dict:
    """
    Demande de réinitialisation : recherche user par email (IAuthProvider), profil (queries),
    token (règle durée), stockage (IResetTokenStore), envoi email (IEmailSender).
    Retourne toujours le même message (sécurité).
    """
    debug = is_app_debug_enabled()
    try:
        try:
            user_id = auth_provider.find_user_id_by_email(email)
            if not user_id:
                if debug:

                    logger.debug("Password reset : email inconnu dans auth.users")
                return {
                    "message": "Si cet e-mail existe, un lien de réinitialisation a été envoyé"
                }
        except Exception as e:

            logger.warning("Password reset : recherche utilisateur échouée: %s", e)
            return {
                "message": "Si cet e-mail existe, un lien de réinitialisation a été envoyé"
            }

        user_name = get_profile_display_name(user_id, email.split("@")[0])
        reset_token = secrets.token_urlsafe(32)
        expires_at = datetime.now(timezone.utc) + timedelta(
            hours=RESET_TOKEN_VALIDITY_HOURS
        )

        reset_token_repository.create(
            user_id=user_id,
            email=email.lower(),
            token=reset_token,
            expires_at=expires_at.isoformat(),
        )

        email_sent = email_sender.send_password_reset(
            to_email=email,
            reset_token=reset_token,
            user_name=user_name,
        )
        if debug:

            logger.debug("Password reset : email_sent=%s", email_sent)

        return {
            "message": "Si cet e-mail existe, un lien de réinitialisation a été envoyé"
        }

    except Exception as e:

        logger.warning("Password reset : erreur interne: %s", e, exc_info=debug)
        return {
            "message": "Si cet e-mail existe, un lien de réinitialisation a été envoyé"
        }


def reset_password(token: str, new_password: str) -> dict:
    """
    Confirmation reset : token via IResetTokenStore, vérif expiration, update password (IAuthProvider), mark_used.
    """
    debug = is_app_debug_enabled()
    try:
        try:
            token_data = reset_token_repository.get_valid(token)
        except Exception as e:
            mapped = _reset_password_client_error(e)
            if mapped:
                logger.warning("Password reset get_valid: %s", e, exc_info=debug)
                raise mapped
            raise
        if not token_data:
            raise HTTPException(status_code=400, detail="Token invalide ou expiré")

        expires_at = datetime.fromisoformat(
            token_data["expires_at"].replace("Z", "+00:00")
        )
        if datetime.now(expires_at.tzinfo) > expires_at:
            raise HTTPException(status_code=400, detail="Token expiré")

        auth_provider.update_user_password(token_data["user_id"], new_password)
        reset_token_repository.mark_used(token)

        if debug:

            logger.debug("Password reset confirmé pour user_id=%s", token_data["user_id"])

        return {"message": "Mot de passe réinitialisé avec succès"}

    except HTTPException:
        raise
    except Exception as e:
        mapped = _reset_password_client_error(e)
        if mapped:
            logger.warning("Password reset confirmation: %s", e, exc_info=debug)
            raise mapped

        logger.error("Password reset confirmation: %s", e, exc_info=debug)
        raise HTTPException(
            status_code=500,
            detail="Erreur lors de la réinitialisation du mot de passe",
        )


def change_password(
    user_id: str,
    user_email: str,
    current_password: str,
    new_password: str,
) -> dict:
    """
    Changement mot de passe (utilisateur connecté) : vérifie current via sign_in, puis update via IAuthProvider.
    """
    debug = is_app_debug_enabled()
    try:
        try:
            auth_provider.sign_in_with_password(user_email, current_password)
        except HTTPException:
            raise
        except Exception as auth_error:

            logger.info("Change password : vérification actuelle échouée: %s", auth_error)
            raise HTTPException(
                status_code=400,
                detail="Mot de passe actuel incorrect",
            )

        auth_provider.update_user_password(user_id, new_password)
        set_must_change_password(user_id, False)
        if debug:

            logger.debug("Change password réussi pour user_id=%s", user_id)
        return {"message": "Mot de passe modifié avec succès"}

    except HTTPException:
        raise
    except Exception as e:

        logger.error("Change password : %s", e, exc_info=debug)
        raise HTTPException(
            status_code=500,
            detail="Erreur lors du changement de mot de passe",
        )


def logout() -> dict:
    """Déconnexion : IAuthProvider.sign_out."""
    try:
        auth_provider.sign_out()
        return {"message": "Déconnexion réussie"}
    except Exception:
        return {"message": "Déconnexion réussie"}
