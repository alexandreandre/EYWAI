"""
Service applicatif mutuelle_types : orchestration des cas d’usage.

Utilise le repository (interface domain) et les règles métier (domain).
Pas d’accès DB direct ; pas de FastAPI dans les dépendances domain.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException

from app.modules.mutuelle_types.domain.entities import MutuelleType
from app.modules.mutuelle_types.domain.rules import (
    message_libelle_deja_existant,
    message_libelle_deja_existant_avec_statut,
    statut_formule,
)
from app.modules.mutuelle_types.infrastructure.mappers import (
    entity_to_response_dict,
)
from app.modules.mutuelle_types.schemas import (
    MutuelleTypeCreate,
    MutuelleTypeUpdate,
)


class MutuelleTypesService:
    """Orchestration list / create / update / delete formules mutuelle via repository."""

    def __init__(self, repository: object) -> None:
        self._repo = repository

    def list_by_company(self, company_id: str) -> list[dict]:
        """Liste les formules mutuelle du catalogue avec employee_ids pour chaque formule."""
        entities = self._repo.list_by_company(company_id)
        result = []
        for entity in entities:
            employee_ids = self._repo.list_employee_ids(str(entity.id))
            result.append(
                entity_to_response_dict(entity, employee_ids)
            )
        return result

    def create(
        self,
        company_id: str,
        created_by: str,
        payload: MutuelleTypeCreate,
    ) -> dict:
        """Crée une formule et gère les associations employés + sync specificites_paie."""
        existing = self._repo.find_by_company_and_libelle(
            company_id, payload.libelle
        )
        if existing is not None:
            raise HTTPException(
                status_code=400,
                detail=message_libelle_deja_existant_avec_statut(
                    payload.libelle,
                    statut_formule(existing.is_active),
                ),
            )
        entity = MutuelleType(
            id=None,
            company_id=UUID(company_id),
            libelle=payload.libelle,
            montant_salarial=payload.montant_salarial,
            montant_patronal=payload.montant_patronal,
            part_patronale_soumise_a_csg=payload.part_patronale_soumise_a_csg,
            is_active=payload.is_active,
            created_at=None,
            updated_at=None,
            created_by=None,
        )
        created = self._repo.create(entity, created_by)
        mutuelle_id = str(created.id)
        employee_ids = list(payload.employee_ids or [])
        valid_ids = []
        if employee_ids:
            valid_ids = self._repo.validate_employee_ids_belong_to_company(
                company_id, employee_ids
            )
            if len(valid_ids) != len(employee_ids):
                raise HTTPException(
                    status_code=400,
                    detail="Certains employés sélectionnés n'appartiennent pas à votre entreprise",
                )
            self._repo.set_employee_associations(
                mutuelle_id, valid_ids, created_by, company_id
            )
        return entity_to_response_dict(created, valid_ids)

    def update(
        self,
        mutuelle_type_id: str,
        company_id: str,
        created_by: str,
        payload: MutuelleTypeUpdate,
    ) -> dict:
        """Met à jour une formule et gère le diff des associations + sync specificites_paie."""
        existing = self._repo.get_by_id(mutuelle_type_id, company_id)
        if existing is None:
            raise HTTPException(
                status_code=404, detail="Formule de mutuelle non trouvée"
            )
        if str(existing.company_id) != company_id:
            raise HTTPException(
                status_code=403,
                detail="Cette formule de mutuelle n'appartient pas à votre entreprise",
            )
        update_data = {
            k: v
            for k, v in payload.model_dump().items()
            if v is not None
        }
        employee_ids = update_data.pop("employee_ids", None)
        if "libelle" in update_data:
            other = self._repo.find_by_company_and_libelle(
                company_id,
                update_data["libelle"],
                exclude_id=mutuelle_type_id,
            )
            if other is not None:
                raise HTTPException(
                    status_code=400,
                    detail=message_libelle_deja_existant(
                        update_data["libelle"],
                    ),
                )
        updated = self._repo.update(mutuelle_type_id, update_data)
        if updated is None:
            raise HTTPException(
                status_code=500, detail="Erreur lors de la mise à jour"
            )
        if employee_ids is not None:
            valid_ids = self._repo.validate_employee_ids_belong_to_company(
                company_id, employee_ids
            )
            if employee_ids and len(valid_ids) != len(employee_ids):
                raise HTTPException(
                    status_code=400,
                    detail="Certains employés sélectionnés n'appartiennent pas à votre entreprise",
                )
            self._repo.set_employee_associations(
                mutuelle_type_id, valid_ids, created_by, company_id
            )
        ids_after = self._repo.list_employee_ids(mutuelle_type_id)
        return entity_to_response_dict(updated, ids_after)

    def delete(self, mutuelle_type_id: str, company_id: str) -> dict:
        """Supprime la formule, retire les associations et sync specificites_paie des employés."""
        existing = self._repo.get_by_id(mutuelle_type_id, company_id)
        if existing is None:
            raise HTTPException(
                status_code=404, detail="Formule de mutuelle non trouvée"
            )
        if str(existing.company_id) != company_id:
            raise HTTPException(
                status_code=403,
                detail="Cette formule de mutuelle n'appartient pas à votre entreprise",
            )
        employee_ids = self._repo.list_employee_ids(mutuelle_type_id)
        self._repo.remove_employee_associations_and_sync_specificites(
            mutuelle_type_id, employee_ids
        )
        self._repo.delete(mutuelle_type_id)
        return {
            "status": "success",
            "message": "Formule de mutuelle supprimée avec succès",
        }
