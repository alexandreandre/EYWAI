"""
Providers : services externes (Auth, PDF, Storage).

Comportement identique aux appels des anciens routers.
"""
from pathlib import Path
from typing import Any

from app.core.database import get_supabase_admin_client, supabase

from app.modules.users.domain.interfaces import (
    IAuthProvider,
    ICredentialsPdfProvider,
    IStorageProvider,
)


class SupabaseAuthProvider(IAuthProvider):
    """Supabase Auth Admin API."""

    def __init__(self):
        self._client = None

    def _get_client(self):
        if self._client is None:
            self._client = get_supabase_admin_client()
        return self._client

    def create_user(
        self, email: str, password: str, metadata: dict
    ) -> Any:
        client = self._get_client()
        r = client.auth.admin.create_user({
            "email": email,
            "password": password,
            "email_confirm": True,
            "user_metadata": metadata,
        })
        return r

    def get_user_by_id(self, user_id: str) -> Any:
        client = self._get_client()
        return client.auth.admin.get_user_by_id(user_id)

    def delete_user(self, user_id: str) -> None:
        client = self._get_client()
        client.auth.admin.delete_user(user_id)


class CredentialsPdfProvider(ICredentialsPdfProvider):
    """Génération PDF création de compte (services.pdf_generator)."""

    def get_logo_path(self) -> str:
        # backend_api/app/modules/users/infrastructure/providers.py -> backend_api
        backend_root = Path(__file__).resolve().parent.parent.parent.parent.parent
        return str(backend_root / "frontend" / "public" / "Colorplast.png")

    def generate(
        self,
        first_name: str,
        last_name: str,
        username: str,
        password: str,
        logo_path: str,
    ) -> bytes:
        from app.shared.infrastructure.pdf import generate_credentials_pdf
        return generate_credentials_pdf(
            first_name=first_name,
            last_name=last_name,
            username=username,
            password=password,
            logo_path=logo_path,
        )


class SupabaseStorageProvider(IStorageProvider):
    """Upload PDF credentials dans le bucket creation_compte."""

    BUCKET = "creation_compte"

    def upload_credentials_pdf(
        self, company_id: str, user_id: str, content: bytes
    ) -> str:
        path = f"{company_id}/{user_id}/creation_compte.pdf"
        supabase.storage.from_(self.BUCKET).upload(
            path=path,
            file=content,
            file_options={"x-upsert": "true", "content-type": "application/pdf"},
        )
        return path


# Instances partagées
auth_provider = SupabaseAuthProvider()
credentials_pdf_provider = CredentialsPdfProvider()
storage_provider = SupabaseStorageProvider()
