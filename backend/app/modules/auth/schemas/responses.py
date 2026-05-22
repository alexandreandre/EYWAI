# Schémas de sortie API du module auth (migration depuis api/routers/auth.py).
# Comportement identique : Token, TokenWithUser (user = User partagé app.modules.users).

from pydantic import BaseModel

from app.modules.users.schemas import User


class Token(BaseModel):
    access_token: str
    token_type: str
    refresh_token: str | None = None
    expires_in: int | None = None
    expires_at: int | None = None


class TokenWithUser(BaseModel):
    access_token: str
    token_type: str
    refresh_token: str | None = None
    expires_in: int | None = None
    expires_at: int | None = None
    user: User


class RefreshTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    refresh_token: str | None = None
    expires_in: int | None = None
    expires_at: int | None = None
