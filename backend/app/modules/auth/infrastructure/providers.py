# Implémentations des ports auth : Supabase Auth, résolution email (employees), envoi email, user from token.
# Comportement strictement identique au code legacy.

from __future__ import annotations

from app.core.database import get_supabase_admin_client, supabase
from app.core.security import get_current_user
from app.core.settings import SUPABASE_KEY, SUPABASE_URL
from app.modules.auth.domain.interfaces import (
    IAuthProvider,
    IEmailSender,
    IUserByLoginResolver,
    IUserFromToken,
)
from supabase import create_client


class SupabaseAuthProvider(IAuthProvider):
    """Délègue à Supabase Auth (client frais pour sign_in, admin pour update/list)."""

    def sign_in_with_password(self, email: str, password: str) -> dict:
        auth_client = create_client(SUPABASE_URL, SUPABASE_KEY)
        res = auth_client.auth.sign_in_with_password(
            {"email": email, "password": password}
        )
        return {
            "access_token": res.session.access_token,
            "user": res.user,
        }

    def sign_out(self) -> None:
        supabase.auth.sign_out()

    def update_user_password(self, user_id: str, new_password: str) -> None:
        admin_client = get_supabase_admin_client()
        admin_client.auth.admin.update_user_by_id(
            user_id,
            {"password": new_password},
        )

    def get_user_by_token(self, token: str):
        return supabase.auth.get_user(token).user

    def find_user_id_by_email(self, email: str) -> str | None:
        admin_client = get_supabase_admin_client()
        users_response = admin_client.auth.admin.list_users()
        for u in users_response:
            if u.email and u.email.lower() == email.lower():
                return u.id
        return None


class UserByLoginResolver(IUserByLoginResolver):
    """Résout username → email via table employees (Supabase)."""

    def resolve_email(self, username_or_email: str) -> str | None:
        from app.modules.auth.domain.rules import is_email_like

        login_input = username_or_email.strip().lower()
        if is_email_like(login_input):
            return login_input
        resp = (
            supabase.table("employees")
            .select("email, username")
            .eq("username", login_input)
            .execute()
        )
        if not resp.data or len(resp.data) == 0:
            return None
        return resp.data[0]["email"]


class EmailSenderProvider(IEmailSender):
    """Envoi e-mail réinitialisation via `app.shared.infrastructure.email` (SMTP)."""

    def send_password_reset(
        self,
        to_email: str,
        reset_token: str,
        user_name: str | None = None,
    ) -> bool:
        from app.shared.infrastructure.email import send_password_reset_email

        return send_password_reset_email(
            to_email=to_email,
            reset_token=reset_token,
            user_name=user_name,
        )


class UserFromTokenProvider(IUserFromToken):
    """Récupère le User (profil, entreprises) à partir du token JWT via app.core.security."""

    def get_user(self, token: str):
        return get_current_user(token=token)
