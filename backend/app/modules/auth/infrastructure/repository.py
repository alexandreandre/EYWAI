# Persistance des tokens de réinitialisation (table password_resets).
# Implémente IResetTokenStore. Comportement identique au code legacy.

from __future__ import annotations

from app.core.database import supabase
from app.modules.auth.domain.interfaces import IResetTokenStore


class PasswordResetTokenRepository(IResetTokenStore):
    """Implémentation Supabase pour la table password_resets."""

    def create(self, user_id: str, email: str, token: str, expires_at: str) -> None:
        reset_data = {
            "user_id": user_id,
            "email": email.lower(),
            "token": token,
            "expires_at": expires_at,
            "used": False,
        }
        supabase.table("password_resets").insert(reset_data).execute()

    def get_valid(self, token: str) -> dict | None:
        resp = (
            supabase.table("password_resets")
            .select("*")
            .eq("token", token)
            .eq("used", False)
            .execute()
        )
        if not resp.data or len(resp.data) == 0:
            return None
        return resp.data[0]

    def mark_used(self, token: str) -> None:
        supabase.table("password_resets").update({"used": True}).eq(
            "token", token
        ).execute()
