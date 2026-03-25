"""
Commandes applicatives (write) pour mutuelle_types.

Délèguent au service (repository injecté) ; gèrent APIError 23505 (contrainte unique).
"""

from __future__ import annotations

import traceback

from fastapi import HTTPException
from postgrest.exceptions import APIError

from app.core.database import supabase
from app.modules.mutuelle_types.application.service import MutuelleTypesService
from app.modules.mutuelle_types.domain.rules import message_libelle_deja_existant
from app.modules.mutuelle_types.infrastructure.repository import (
    SupabaseMutuelleTypeRepository,
)
from app.modules.mutuelle_types.schemas import (
    MutuelleTypeCreate,
    MutuelleTypeUpdate,
)


def create_mutuelle_type(
    company_id: str,
    created_by: str,
    payload: MutuelleTypeCreate,
) -> dict:
    """
    Crée une formule de mutuelle et gère les associations employés.
    Lève HTTPException 400 (libellé dupliqué, employés invalides), 500 en cas d’erreur.
    """
    try:
        repo = SupabaseMutuelleTypeRepository(supabase)
        service = MutuelleTypesService(repo)
        return service.create(company_id, created_by, payload)
    except HTTPException:
        raise
    except APIError as e:
        error_dict = e.args[0] if e.args and isinstance(e.args[0], dict) else {}
        if error_dict.get("code") == "23505":
            msg = error_dict.get("message", "")
            if "unique_mutuelle_type_per_company" in msg:
                raise HTTPException(
                    status_code=400,
                    detail=message_libelle_deja_existant(payload.libelle),
                )
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail="Erreur lors de la création de la formule de mutuelle",
        )
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors de la création de la formule de mutuelle: {str(e)}",
        )


def update_mutuelle_type(
    mutuelle_type_id: str,
    company_id: str,
    created_by: str,
    payload: MutuelleTypeUpdate,
) -> dict:
    """
    Met à jour une formule et gère le diff des associations employés.
    Lève HTTPException 404, 403, 400 (libellé dupliqué, employés invalides), 500 en cas d’erreur.
    """
    try:
        repo = SupabaseMutuelleTypeRepository(supabase)
        service = MutuelleTypesService(repo)
        return service.update(mutuelle_type_id, company_id, created_by, payload)
    except HTTPException:
        raise
    except APIError as e:
        error_dict = e.args[0] if e.args and isinstance(e.args[0], dict) else {}
        if error_dict.get("code") == "23505":
            msg = error_dict.get("message", "")
            if "unique_mutuelle_type_per_company" in msg:
                libelle = payload.libelle or "ce libellé"
                raise HTTPException(
                    status_code=400,
                    detail=message_libelle_deja_existant(libelle),
                )
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail="Erreur lors de la mise à jour",
        )
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors de la mise à jour: {str(e)}",
        )


def delete_mutuelle_type(mutuelle_type_id: str, company_id: str) -> dict:
    """
    Supprime une formule, retire les associations et met à jour specificites_paie des employés.
    Lève HTTPException 404, 403, 500 en cas d’erreur.
    """
    try:
        repo = SupabaseMutuelleTypeRepository(supabase)
        service = MutuelleTypesService(repo)
        return service.delete(mutuelle_type_id, company_id)
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors de la suppression: {str(e)}",
        )
