# Renouvellement silencieux du JWT d'accès via le refresh token Supabase.

from __future__ import annotations

from fastapi import HTTPException

from app.modules.auth.infrastructure import auth_provider


def refresh_tokens(refresh_token: str) -> dict:
    """
    Échange un refresh_token valide contre un nouvel access_token (et refresh si rotation).
    Lève HTTP 401 si le refresh token est invalide ou expiré.
    """
    token = (refresh_token or "").strip()
    if not token:
        raise HTTPException(
            status_code=401,
            detail="Session expirée. Veuillez vous reconnecter.",
        )
    try:
        session = auth_provider.refresh_session(token)
    except Exception:
        raise HTTPException(
            status_code=401,
            detail="Session expirée. Veuillez vous reconnecter.",
        ) from None

    return {
        "access_token": session["access_token"],
        "token_type": "bearer",
        "refresh_token": session.get("refresh_token"),
        "expires_in": session.get("expires_in"),
        "expires_at": session.get("expires_at"),
    }
