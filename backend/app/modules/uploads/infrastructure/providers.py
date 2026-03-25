"""
Provider storage pour le bucket Supabase 'logos'.

Implémente ILogoStorage (domain). Comportement identique à api/routers/uploads.py.
"""
from __future__ import annotations

from app.core.database import supabase

from app.modules.uploads.domain.interfaces import ILogoStorage

BUCKET_LOGOS = "logos"


class LogoStorage:
    """Implémentation Supabase de ILogoStorage (bucket 'logos')."""

    def upload(self, path: str, content: bytes, content_type: str) -> None:
        """
        Envoie le fichier au bucket 'logos'. Lève en cas d'erreur.
        path : chemin dans le bucket (ex. logos/companies/company_xxx_uuid.png).
        """
        supabase.storage.from_(BUCKET_LOGOS).upload(
            path,
            content,
            file_options={"content-type": content_type},
        )

    def get_public_url(self, path: str) -> str:
        """Retourne l'URL publique du fichier."""
        return supabase.storage.from_(BUCKET_LOGOS).get_public_url(path)

    def remove(self, paths: list[str]) -> None:
        """
        Supprime les fichiers du bucket 'logos'.
        En cas d'erreur, log et continue (comportement legacy).
        """
        try:
            supabase.storage.from_(BUCKET_LOGOS).remove(paths)
        except Exception as e:
            print(
                f"Avertissement: impossible de supprimer le fichier du storage: {e}"
            )


_default_storage: ILogoStorage = LogoStorage()


def upload_logo_file(path: str, content: bytes, content_type: str) -> None:
    """
    Envoie le fichier au bucket 'logos'. Lève en cas d'erreur.
    path : chemin dans le bucket (ex. logos/companies/company_xxx_uuid.png).
    """
    _default_storage.upload(path, content, content_type)


def get_logo_public_url(path: str) -> str:
    """Retourne l'URL publique du fichier."""
    return _default_storage.get_public_url(path)


def remove_logo_files(paths: list[str]) -> None:
    """
    Supprime les fichiers du bucket 'logos'.
    En cas d'erreur, log et continue (comportement legacy).
    """
    _default_storage.remove(paths)
