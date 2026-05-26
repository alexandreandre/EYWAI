# Orchestration login : résolution identifiant, sign_in, construction TokenWithUser.
# Utilise uniquement domain (règles) + infrastructure (ports). Comportement identique au legacy.

from __future__ import annotations

from fastapi import HTTPException

from app.core.logging import get_logger, is_app_debug_enabled
from app.modules.auth.domain.rules import is_email_like
from app.modules.auth.infrastructure import (
    auth_provider,
    user_from_token,
    user_resolver,
)

logger = get_logger("modules.auth")


def login(username_or_email: str, password: str) -> dict:
    """
    Connexion : si pas email (règle is_email_like), résout l’email via IUserByLoginResolver ;
    puis sign_in_with_password ; puis User via IUserFromToken.
    Retourne {"access_token", "token_type": "bearer", "user": User}.
    """
    debug = is_app_debug_enabled()
    try:
        login_input = username_or_email.strip().lower()

        if is_email_like(login_input):
            email_to_use = login_input
        else:
            if debug:

                logger.debug("Résolution username → email pour identifiant fourni")
            email_to_use = user_resolver.resolve_email(login_input)
            if not email_to_use:
                if debug:

                    logger.debug(
                        "Échec login : aucun employé pour cet identifiant (count=%s)",
                        _employee_count_hint(),
                    )
                raise HTTPException(
                    status_code=400, detail="Identifiant ou mot de passe incorrect"
                )

        if not email_to_use:
            raise HTTPException(
                status_code=400, detail="Identifiant ou mot de passe incorrect"
            )

        session = auth_provider.sign_in_with_password(email_to_use, password)
        access_token = session["access_token"]
        user_info = user_from_token.get_user(access_token)

        if debug:

            logger.debug(
                "Connexion réussie (super_admin=%s)",
                user_info.is_super_admin,
            )

        return {
            "access_token": access_token,
            "token_type": "bearer",
            "refresh_token": session.get("refresh_token"),
            "expires_in": session.get("expires_in"),
            "expires_at": session.get("expires_at"),
            "user": user_info,
        }

    except HTTPException:
        raise
    except Exception as e:

        logger.warning("Échec login inattendu: %s", type(e).__name__, exc_info=debug)
        raise HTTPException(
            status_code=400, detail="Identifiant ou mot de passe incorrect"
        )


def _employee_count_hint() -> str:
    """Indicateur agrégé pour le debug local (pas de dump PII)."""
    try:
        from app.modules.auth.infrastructure.queries import get_employees_debug_snapshot

        return str(len(get_employees_debug_snapshot()))
    except Exception:
        return "?"
