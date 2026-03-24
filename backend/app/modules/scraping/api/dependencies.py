"""
Dépendances FastAPI du module scraping.

Vérification super admin : à brancher sur access_control ou à garder ici
lors de la migration (comportement identique au legacy).
"""
from __future__ import annotations

from fastapi import Depends, HTTPException, status

from app.core.database import supabase
from app.core.security import get_current_user
from app.modules.users.schemas.responses import User


async def verify_super_admin(
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    Vérifie que l'utilisateur connecté est un super admin.
    Retourne la ligne super_admins pour usage optionnel ; lève 403 sinon.
    """
    try:
        result = (
            supabase.table("super_admins")
            .select("*")
            .eq("user_id", current_user.id)
            .eq("is_active", True)
            .execute()
        )
        if not result.data or len(result.data) == 0:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Accès refusé : vous devez être super administrateur",
            )
        return result.data[0]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Erreur lors de la vérification : {str(e)}",
        )
