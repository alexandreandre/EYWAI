# Schémas de sortie API du module auth (migration depuis api/routers/auth.py).
# Comportement identique : Token, TokenWithUser (user = User partagé app.modules.users).

from pydantic import BaseModel

from app.modules.users.schemas import User


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenWithUser(BaseModel):
    access_token: str
    token_type: str
    user: User
