# Dépendances API du module exports (préparation migration).
# get_active_company_id : à terme peut être mutualisé dans app.api.dependencies ou app.core.
from typing import Optional
from fastapi import Header, HTTPException


def get_active_company_id(x_active_company: Optional[str] = Header(None)) -> str:
    """Récupère l'ID de l'entreprise active depuis le header X-Active-Company."""
    if not x_active_company:
        raise HTTPException(
            status_code=400,
            detail="X-Active-Company header is required",
        )
    return x_active_company
