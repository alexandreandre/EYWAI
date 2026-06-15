"""Dépendances FastAPI import DSN."""

from __future__ import annotations

from fastapi import Depends, HTTPException, status

from app.core.database import supabase
from app.core.security import get_current_user


async def verify_super_admin(current_user=Depends(get_current_user)) -> dict:
    try:
        result = (
            supabase.table("super_admins")
            .select("*")
            .eq("user_id", current_user.id)
            .eq("is_active", True)
            .execute()
        )
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Accès refusé : super administrateur requis",
            )
        return result.data[0]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Erreur lors de la vérification : {e}",
        ) from e
