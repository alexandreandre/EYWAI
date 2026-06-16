"""Dépendances FastAPI import DSN."""

from __future__ import annotations

from fastapi import Depends, HTTPException, Query, status

from app.core.database import supabase
from app.core.security import get_current_user
from app.modules.companies.application.service import resolve_company_id_for_user
from app.modules.dsn_import.infrastructure import repository as repo


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


async def verify_super_admin_or_company_access(
    company_id: str = Query(..., description="Identifiant entreprise"),
    current_user=Depends(get_current_user),
) -> dict:
    """Super-admin ou utilisateur RH avec accès à l'entreprise."""
    try:
        result = (
            supabase.table("super_admins")
            .select("*")
            .eq("user_id", current_user.id)
            .eq("is_active", True)
            .execute()
        )
        if result.data:
            return {"role": "super_admin", "company_id": company_id}
    except Exception:
        pass

    active = resolve_company_id_for_user(current_user)
    target = company_id or active
    if not target:
        raise HTTPException(status_code=400, detail="Aucune entreprise spécifiée")
    if not current_user.has_access_to_company(target):
        raise HTTPException(status_code=403, detail="Accès non autorisé pour cette entreprise")
    company = repo.find_company_by_id(target)
    if not company:
        raise HTTPException(status_code=404, detail="Entreprise introuvable")
    return {"role": "company_user", "company_id": target, "company": company}
