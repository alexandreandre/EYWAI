# Stockage des fichiers d'export (Supabase Storage).
# Comportement identique à api/routers/exports.upload_export_file et signed URL.
import time
from app.core.database import supabase

BUCKET_EXPORTS = "exports"
SIGNED_URL_EXPIRES_SEC = 3600


def upload_export_file(
    bucket: str,
    storage_path: str,
    file_content: bytes,
    content_type: str,
) -> str:
    """
    Upload un fichier d'export dans Supabase Storage avec gestion des doublons.
    Returns:
        str: Le chemin final du fichier uploadé (peut différer si doublon)
    """
    try:
        supabase.storage.from_(bucket).upload(
            storage_path,
            file_content,
            file_options={"content-type": content_type, "upsert": "true"},
        )
        return storage_path
    except Exception as e:
        if "409" in str(e) or "Duplicate" in str(e):
            parts = storage_path.rsplit("/", 1)
            if len(parts) == 2:
                directory, filename = parts
                name, ext = (
                    filename.rsplit(".", 1) if "." in filename else (filename, "")
                )
                timestamp = int(time.time() * 1000)
                new_filename = (
                    f"{name}_{timestamp}.{ext}" if ext else f"{name}_{timestamp}"
                )
                new_storage_path = f"{directory}/{new_filename}"
            else:
                name, ext = (
                    storage_path.rsplit(".", 1)
                    if "." in storage_path
                    else (storage_path, "")
                )
                timestamp = int(time.time() * 1000)
                new_storage_path = (
                    f"{name}_{timestamp}.{ext}" if ext else f"{name}_{timestamp}"
                )
            supabase.storage.from_(bucket).upload(
                new_storage_path,
                file_content,
                file_options={"content-type": content_type, "upsert": "true"},
            )
            return new_storage_path
        raise


def create_signed_url(path: str, expires_sec: int = SIGNED_URL_EXPIRES_SEC) -> str:
    """Génère une URL signée pour un fichier dans le bucket exports."""
    response = supabase.storage.from_(BUCKET_EXPORTS).create_signed_url(
        path, expires_sec
    )
    return response.get("signedURL") or response.get("signedUrl", "")
