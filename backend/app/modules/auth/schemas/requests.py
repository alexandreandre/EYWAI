# Schémas d'entrée API du module auth (migration depuis api/routers/auth.py).
# Comportement identique : mêmes champs, mêmes contrats.

from pydantic import BaseModel, EmailStr, field_validator

from app.modules.activation.domain.rules import validate_activation_password


def _valider_mot_de_passe(valeur: str) -> str:
    """MÊME règle que l'activation : 8 caractères, majuscule, minuscule, chiffre.

    Sans cela, un salarié contournait la politique en passant par
    « mot de passe oublié » (audit sécurité 23/08/2026).
    """
    erreur = validate_activation_password(valeur)
    if erreur:
        raise ValueError(erreur)
    return valeur


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str

    _valider = field_validator("new_password")(_valider_mot_de_passe)


class PasswordChange(BaseModel):
    current_password: str
    new_password: str

    _valider = field_validator("new_password")(_valider_mot_de_passe)


class RefreshTokenRequest(BaseModel):
    refresh_token: str
