"""
Requêtes applicatives (read) pour mutuelle_types.

Délègue au service (repository injecté) ; pas d’accès DB direct ici.
"""
from __future__ import annotations

import traceback

from fastapi import HTTPException

from app.core.database import supabase
from app.modules.mutuelle_types.application.service import MutuelleTypesService
from app.modules.mutuelle_types.infrastructure.repository import (
    SupabaseMutuelleTypeRepository,
)


def list_mutuelle_types(company_id: str) -> list[dict]:
    """
    Liste les formules mutuelle du catalogue pour une entreprise (avec employee_ids).
    Lève HTTPException 400 si company_id manquant, 500 en cas d’erreur.
    """
    try:
        repo = SupabaseMutuelleTypeRepository(supabase)
        service = MutuelleTypesService(repo)
        return service.list_by_company(company_id)
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors de la récupération des mutuelles: {str(e)}",
        )
