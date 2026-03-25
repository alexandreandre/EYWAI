"""
Service d'orchestration partagé pour le module uploads.

Factorise la vérification des droits et la validation entity_type (comportement legacy).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import HTTPException

from app.modules.uploads.domain.rules import (
    ALLOWED_LOGO_MIMETYPES,
    MAX_LOGO_SIZE_BYTES,
    is_valid_entity_type,
)
from app.modules.uploads.infrastructure import queries as infra_queries

if TYPE_CHECKING:
    from app.modules.users.schemas.responses import User


def ensure_can_edit_entity_logo(
    entity_type: str,
    entity_id: str,
    current_user: "User",
) -> None:
    """
    Vérifie que l'utilisateur peut modifier le logo de l'entité.
    Lève HTTPException 403 ou 400 avec les messages exacts du legacy.
    """
    if not is_valid_entity_type(entity_type):
        raise HTTPException(
            status_code=400,
            detail="entity_type doit être 'company' ou 'group'",
        )

    allowed = infra_queries.can_edit_entity_logo(
        user_id=current_user.id,
        is_super_admin=current_user.is_super_admin,
        entity_type=entity_type,
        entity_id=entity_id,
    )
    if not allowed:
        if entity_type == "company":
            raise HTTPException(
                status_code=403,
                detail="Vous devez être administrateur de cette entreprise",
            )
        raise HTTPException(
            status_code=403,
            detail="Vous devez être super administrateur pour modifier un groupe",
        )


def validate_logo_file(
    content_type: str | None,
    size_bytes: int,
) -> None:
    """
    Vérifie type MIME et taille du fichier logo.
    Lève HTTPException 400 avec les messages exacts du legacy.
    """
    if not content_type or content_type not in ALLOWED_LOGO_MIMETYPES:
        allowed_str = ", ".join(sorted(ALLOWED_LOGO_MIMETYPES))
        raise HTTPException(
            status_code=400,
            detail=f"Type de fichier non autorisé. Types autorisés : {allowed_str}",
        )
    if size_bytes > MAX_LOGO_SIZE_BYTES:
        max_mb = MAX_LOGO_SIZE_BYTES / (1024 * 1024)
        raise HTTPException(
            status_code=400,
            detail=f"Le fichier est trop volumineux. Taille maximale : {max_mb} MB",
        )
