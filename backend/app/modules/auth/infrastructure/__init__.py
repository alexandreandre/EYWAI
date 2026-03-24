# Couche infrastructure du module auth.
# Instances partagées pour l’application (comportement identique au legacy).

from app.modules.auth.infrastructure.providers import (
    EmailSenderProvider,
    SupabaseAuthProvider,
    UserByLoginResolver,
    UserFromTokenProvider,
)
from app.modules.auth.infrastructure.repository import PasswordResetTokenRepository

# Instances utilisées par la couche application
auth_provider = SupabaseAuthProvider()
user_resolver = UserByLoginResolver()
email_sender = EmailSenderProvider()
user_from_token = UserFromTokenProvider()
reset_token_repository = PasswordResetTokenRepository()

__all__ = [
    "EmailSenderProvider",
    "PasswordResetTokenRepository",
    "SupabaseAuthProvider",
    "UserByLoginResolver",
    "UserFromTokenProvider",
    "auth_provider",
    "email_sender",
    "reset_token_repository",
    "user_from_token",
    "user_resolver",
]
