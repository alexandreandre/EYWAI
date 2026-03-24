# Router du module auth : délégation à la couche application uniquement.
# Prefix attendu : /api/auth. Comportement HTTP identique au legacy.

from fastapi import APIRouter, Depends, Query
from fastapi.security import OAuth2PasswordRequestForm

from app.core.security import get_current_user
from app.modules.auth.application import (
    change_password,
    get_me,
    login,
    logout,
    request_password_reset,
    reset_password,
    verify_reset_token,
)
from app.modules.auth.schemas import (
    PasswordChange,
    PasswordResetConfirm,
    PasswordResetRequest,
    TokenWithUser,
)
from app.modules.users.schemas import User

router = APIRouter()


@router.post("/login", response_model=TokenWithUser)
def login_route(form_data: OAuth2PasswordRequestForm = Depends()):
    """Connexion : email ou username + mot de passe. Retourne token + user."""
    return login(form_data.username, form_data.password)


@router.get("/me", response_model=User)
def read_users_me(current_user: User = Depends(get_current_user)):
    """Récupère les informations de l'utilisateur connecté."""
    return get_me(current_user)


@router.post("/logout")
def logout_route(current_user: User = Depends(get_current_user)):
    """Déconnexion (révocation du token)."""
    return logout()


@router.post("/request-password-reset")
def request_password_reset_route(request: PasswordResetRequest):
    """Demande de réinitialisation : envoie un email avec lien de reset."""
    return request_password_reset(request.email)


@router.post("/reset-password")
def reset_password_route(request: PasswordResetConfirm):
    """Réinitialise le mot de passe avec le token reçu par email."""
    return reset_password(request.token, request.new_password)


@router.post("/verify-reset-token")
def verify_reset_token_route(token: str = Query(...)):
    """Vérifie si un token de réinitialisation est valide."""
    return verify_reset_token(token)


@router.post("/change-password")
def change_password_route(
    request: PasswordChange,
    current_user: User = Depends(get_current_user),
):
    """Changement de mot de passe (utilisateur connecté)."""
    return change_password(
        user_id=current_user.id,
        user_email=current_user.email or "",
        current_password=request.current_password,
        new_password=request.new_password,
    )
