"""
Service applicatif bonus_types : orquestration des cas d'usage.

Contient la logique métier extraite des anciens routeurs.
Le router du module ne fait qu'appeler ce service et renvoyer les réponses.
"""

from __future__ import annotations

from fastapi import HTTPException

from app.modules.bonus_types.application.dto import (
    BonusCalculationResult,
    BonusTypeCreateInput,
    BonusTypeUpdateInput,
)
from app.modules.bonus_types.domain.entities import BonusType
from app.modules.bonus_types.domain.enums import BonusTypeKind
from app.modules.bonus_types.domain.interfaces import (
    IBonusTypeRepository,
    IEmployeeHoursProvider,
)
from app.modules.bonus_types.domain.rules import compute_bonus_amount
from app.modules.bonus_types.infrastructure.providers import (
    SupabaseEmployeeHoursProvider,
)
from app.modules.bonus_types.infrastructure.repository import (
    SupabaseBonusTypeRepository,
)


class BonusTypesService:
    """Cas d'usage : list, create, update, delete, calculate_amount."""

    def __init__(
        self,
        repository: IBonusTypeRepository,
        hours_provider: IEmployeeHoursProvider | None = None,
    ):
        self._repo = repository
        self._hours = hours_provider

    def list_by_company(self, company_id: str) -> list[BonusType]:
        """Liste les primes du catalogue pour l'entreprise (ordre libelle)."""
        if not company_id:
            raise HTTPException(status_code=400, detail="Aucune entreprise active")
        return self._repo.list_by_company(company_id)

    def get_by_id(
        self,
        bonus_type_id: str,
        company_id: str | None = None,
    ) -> BonusType | None:
        """Retourne une prime par id ; optionnellement vérifie company_id."""
        return self._repo.get_by_id(bonus_type_id, company_id)

    def create(
        self,
        input_data: BonusTypeCreateInput,
        has_rh_access: bool,
    ) -> BonusType:
        """Crée une prime. Vérifications : company_id, has_rh_access."""
        if not input_data.company_id:
            raise HTTPException(status_code=400, detail="Aucune entreprise active")
        if not has_rh_access:
            raise HTTPException(
                status_code=403,
                detail="Seuls les Admin/RH peuvent créer des primes dans le catalogue",
            )
        entity = BonusType(
            id=None,
            company_id=input_data.company_id,
            libelle=input_data.libelle,
            type=BonusTypeKind(input_data.type),
            montant=input_data.montant,
            seuil_heures=input_data.seuil_heures,
            soumise_a_cotisations=input_data.soumise_a_cotisations,
            soumise_a_impot=input_data.soumise_a_impot,
            prompt_ia=input_data.prompt_ia,
            created_at=None,
            updated_at=None,
            created_by=input_data.created_by,
        )
        created = self._repo.create(entity)
        if not created.id:
            raise HTTPException(
                status_code=500,
                detail="Erreur lors de la création de la prime",
            )
        return created

    def update(
        self,
        bonus_type_id: str,
        company_id: str,
        has_rh_access: bool,
        input_data: BonusTypeUpdateInput,
    ) -> BonusType | None:
        """Met à jour une prime ; vérifie entreprise et accès RH."""
        if not company_id:
            raise HTTPException(status_code=400, detail="Aucune entreprise active")
        if not has_rh_access:
            raise HTTPException(
                status_code=403,
                detail="Seuls les Admin/RH peuvent modifier des primes",
            )
        existing = self._repo.get_by_id(bonus_type_id, company_id)
        if not existing:
            raise HTTPException(status_code=404, detail="Prime non trouvée")
        if str(existing.company_id) != company_id:
            raise HTTPException(
                status_code=403,
                detail="Cette prime n'appartient pas à votre entreprise",
            )
        update_data = {}
        if input_data.libelle is not None:
            update_data["libelle"] = input_data.libelle
        if input_data.type is not None:
            update_data["type"] = (
                input_data.type
                if isinstance(input_data.type, str)
                else BonusTypeKind(input_data.type).value
            )
        if input_data.montant is not None:
            update_data["montant"] = input_data.montant
        if input_data.seuil_heures is not None:
            update_data["seuil_heures"] = input_data.seuil_heures
        if input_data.soumise_a_cotisations is not None:
            update_data["soumise_a_cotisations"] = input_data.soumise_a_cotisations
        if input_data.soumise_a_impot is not None:
            update_data["soumise_a_impot"] = input_data.soumise_a_impot
        if input_data.prompt_ia is not None:
            update_data["prompt_ia"] = input_data.prompt_ia
        updated = self._repo.update(bonus_type_id, update_data)
        if not updated:
            raise HTTPException(status_code=500, detail="Erreur lors de la mise à jour")
        return updated

    def delete(
        self,
        bonus_type_id: str,
        company_id: str,
        is_super_admin: bool,
        has_rh_access: bool,
    ) -> bool:
        """Supprime une prime ; vérifie entreprise et (super_admin ou accès RH)."""
        if not company_id:
            raise HTTPException(status_code=400, detail="Aucune entreprise active")
        if not is_super_admin and not has_rh_access:
            raise HTTPException(
                status_code=403,
                detail="Seuls les Admin/RH peuvent supprimer des primes",
            )
        existing = self._repo.get_by_id(bonus_type_id, company_id)
        if not existing:
            raise HTTPException(status_code=404, detail="Prime non trouvée")
        if str(existing.company_id) != company_id:
            raise HTTPException(
                status_code=403,
                detail="Cette prime n'appartient pas à votre entreprise",
            )
        self._repo.delete(bonus_type_id)
        return True

    def calculate_amount(
        self,
        bonus_type_id: str,
        company_id: str,
        employee_id: str,
        year: int,
        month: int,
    ) -> BonusCalculationResult:
        """
        Calcule le montant selon le type (montant_fixe ou selon_heures).
        Règle métier pure dans domain.rules.compute_bonus_amount ; IEmployeeHoursProvider en infrastructure.
        """
        if not company_id:
            raise HTTPException(status_code=400, detail="Aucune entreprise active")
        bonus = self._repo.get_by_id(bonus_type_id, company_id)
        if not bonus:
            raise HTTPException(status_code=404, detail="Prime non trouvée")
        total_hours = 0.0
        if self._hours:
            total_hours = self._hours.get_total_actual_hours(employee_id, year, month)
        try:
            computation = compute_bonus_amount(bonus, total_hours)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        return BonusCalculationResult(
            amount=computation.amount,
            calculated=True,
            total_hours=computation.total_hours,
            seuil=computation.seuil,
            condition_met=computation.condition_met,
        )


# Instance par défaut (pour usage depuis les routers / commands / queries).
_default_repo = SupabaseBonusTypeRepository()
_default_provider = SupabaseEmployeeHoursProvider()


def get_bonus_types_service() -> BonusTypesService:
    """Retourne le service bonus_types (repository + provider par défaut)."""
    return BonusTypesService(_default_repo, _default_provider)
