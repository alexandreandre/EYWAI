# Schémas d'entrée API du module auth (migration depuis api/routers/auth.py).
# Comportement identique : mêmes champs, mêmes contrats.

from pydantic import BaseModel, EmailStr


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str


class PasswordChange(BaseModel):
    current_password: str
    new_password: str
