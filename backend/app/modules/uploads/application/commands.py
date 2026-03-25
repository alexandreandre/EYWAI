"""
Commandes (cas d'usage en écriture) pour le module uploads.

Logique migrée depuis api/routers/uploads.py. Comportement exact conservé.
Les commandes lèvent HTTPException (mêmes codes et messages que le legacy).
"""
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from fastapi import HTTPException

from app.modules.uploads.application.dto import (
    DeleteLogoResult,
    LogoScaleResult,
    UploadLogoResult,
)
from app.modules.uploads.application.service import (
    ensure_can_edit_entity_logo,
    validate_logo_file,
)
from app.modules.uploads.domain.rules import (
    LOGO_SCALE_MAX,
    LOGO_SCALE_MIN,
    is_logo_scale_valid,
)
from app.modules.uploads.infrastructure import providers as storage
from app.modules.uploads.infrastructure import repository as repo
from app.modules.uploads.infrastructure.mappers import storage_path_from_logo_url

if TYPE_CHECKING:
    from app.modules.users.schemas.responses import User


async def upload_logo(
    file_content: bytes,
    content_type: str,
    filename: str,
    entity_type: str,
    entity_id: str,
    current_user: "User",
) -> UploadLogoResult:
    """
    Upload un logo pour une entité (company ou group).
    Vérifie permissions, MIME, taille, upload storage, mise à jour DB.
    Comportement identique à api/routers/uploads.py (upload_logo).
    """
    ensure_can_edit_entity_logo(entity_type, entity_id, current_user)
    validate_logo_file(content_type, len(file_content))

    file_extension = filename.split(".")[-1] if "." in filename else "png"
    unique_filename = f"{entity_type}_{entity_id}_{uuid.uuid4()}.{file_extension}"
    bucket_path = f"logos/{entity_type}s/{unique_filename}"

    try:
        storage.upload_logo_file(bucket_path, file_content, content_type or "image/png")
    except Exception as e:
        print(f"Erreur lors de l'upload vers Storage: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors de l'upload du fichier: {str(e)}",
        ) from e

    public_url = storage.get_logo_public_url(bucket_path)
    updated = repo.update_logo_url(entity_type, entity_id, public_url)

    if not updated:
        try:
            storage.remove_logo_files([bucket_path])
        except Exception:
            pass
        entity_label = entity_type.capitalize()
        raise HTTPException(
            status_code=404,
            detail=f"{entity_label} non trouvé(e)",
        )

    return UploadLogoResult(logo_url=public_url, message="Logo uploadé avec succès")


def delete_logo(
    entity_type: str,
    entity_id: str,
    current_user: "User",
) -> DeleteLogoResult:
    """
    Supprime le logo d'une entité. Vérifie permissions, récupère URL, supprime storage, met à jour DB.
    Comportement identique à api/routers/uploads.py (delete_logo).
    """
    ensure_can_edit_entity_logo(entity_type, entity_id, current_user)

    if not repo.entity_exists(entity_type, entity_id):
        entity_label = entity_type.capitalize()
        raise HTTPException(
            status_code=404,
            detail=f"{entity_label} non trouvé(e)",
        )

    logo_url = repo.get_logo_url(entity_type, entity_id)
    if not logo_url:
        return DeleteLogoResult(message="Aucun logo à supprimer")

    path = storage_path_from_logo_url(logo_url)
    if path:
        storage.remove_logo_files([path])

    repo.update_logo_url(entity_type, entity_id, None)
    return DeleteLogoResult(message="Logo supprimé avec succès")


def update_logo_scale(
    entity_type: str,
    entity_id: str,
    scale: float,
    current_user: "User",
) -> LogoScaleResult:
    """
    Met à jour le facteur de zoom du logo. Vérifie permissions et plage scale, update DB.
    Comportement identique à api/routers/uploads.py (update_logo_scale).
    """
    if not is_logo_scale_valid(scale):
        raise HTTPException(
            status_code=400,
            detail=f"Le facteur de zoom doit être entre {LOGO_SCALE_MIN} et {LOGO_SCALE_MAX}",
        )
    ensure_can_edit_entity_logo(entity_type, entity_id, current_user)

    updated = repo.update_logo_scale(entity_type, entity_id, scale)
    if not updated:
        entity_label = entity_type.capitalize()
        raise HTTPException(
            status_code=404,
            detail=f"{entity_label} non trouvé(e)",
        )

    return LogoScaleResult(
        logo_scale=scale,
        message="Facteur de zoom mis à jour avec succès",
    )
