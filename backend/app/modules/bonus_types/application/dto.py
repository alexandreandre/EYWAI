"""
DTOs applicatifs pour bonus_types.

Entrées/sorties des cas d'usage (create, update, calculate).
Conversion entité -> réponse API et construction des entrées depuis les schémas
exposées ici pour que le router n'appelle que l'application.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from uuid import UUID

if TYPE_CHECKING:
    from app.modules.bonus_types.domain.entities import BonusType


@dataclass
class BonusTypeCreateInput:
    """Entrée pour la création d'une prime (aligné BonusTypeCreate)."""

    libelle: str
    type: str  # BonusTypeKind.value
    montant: float
    seuil_heures: float | None
    soumise_a_cotisations: bool
    soumise_a_impot: bool
    prompt_ia: str | None
    company_id: UUID
    created_by: UUID


@dataclass
class BonusTypeUpdateInput:
    """Entrée pour la mise à jour partielle (aligné BonusTypeUpdate)."""

    libelle: str | None = None
    type: str | None = None
    montant: float | None = None
    seuil_heures: float | None = None
    soumise_a_cotisations: bool | None = None
    soumise_a_impot: bool | None = None
    prompt_ia: str | None = None


@dataclass
class BonusCalculationResult:
    """Résultat du calcul de montant d'une prime."""

    amount: float
    calculated: bool
    total_hours: float | None = None
    seuil: float | None = None
    condition_met: bool | None = None

    def to_dict(self) -> dict[str, Any]:
        """Pour réponse API (comportement identique au legacy)."""
        out: dict[str, Any] = {"amount": self.amount, "calculated": self.calculated}
        if self.total_hours is not None:
            out["total_hours"] = self.total_hours
        if self.seuil is not None:
            out["seuil"] = self.seuil
        if self.condition_met is not None:
            out["condition_met"] = self.condition_met
        return out


def bonus_type_to_response_dict(entity: "BonusType") -> dict[str, Any]:
    """Convertit une entité BonusType en dict pour réponse HTTP (même forme que legacy)."""
    from app.modules.bonus_types.domain.entities import BonusType

    if not isinstance(entity, BonusType):
        raise TypeError("entity must be BonusType")
    return {
        "id": str(entity.id) if entity.id else None,
        "company_id": str(entity.company_id),
        "libelle": entity.libelle,
        "type": entity.type.value,
        "montant": entity.montant,
        "seuil_heures": entity.seuil_heures,
        "soumise_a_cotisations": entity.soumise_a_cotisations,
        "soumise_a_impot": entity.soumise_a_impot,
        "prompt_ia": entity.prompt_ia,
        "created_at": entity.created_at.isoformat() if entity.created_at else None,
        "updated_at": entity.updated_at.isoformat() if entity.updated_at else None,
        "created_by": str(entity.created_by) if entity.created_by else None,
    }


def build_create_input(
    payload: Any,  # BonusTypeCreate
    company_id: str,
    user_id: str,
) -> BonusTypeCreateInput:
    """Construit BonusTypeCreateInput à partir du schéma de requête et du contexte utilisateur."""
    from app.modules.bonus_types.schemas.requests import BonusTypeCreate

    if not isinstance(payload, BonusTypeCreate):
        raise TypeError("payload must be BonusTypeCreate")
    type_val = getattr(payload.type, "value", payload.type)
    return BonusTypeCreateInput(
        libelle=payload.libelle,
        type=type_val,
        montant=payload.montant,
        seuil_heures=payload.seuil_heures,
        soumise_a_cotisations=payload.soumise_a_cotisations,
        soumise_a_impot=payload.soumise_a_impot,
        prompt_ia=payload.prompt_ia,
        company_id=UUID(str(company_id)),
        created_by=UUID(str(user_id)),
    )


def build_update_input(payload: Any) -> BonusTypeUpdateInput:  # BonusTypeUpdate
    """Construit BonusTypeUpdateInput à partir du schéma de requête (champs optionnels)."""
    from app.modules.bonus_types.schemas.requests import BonusTypeUpdate

    if not isinstance(payload, BonusTypeUpdate):
        raise TypeError("payload must be BonusTypeUpdate")
    type_val = (
        getattr(payload.type, "value", payload.type)
        if payload.type is not None
        else None
    )
    return BonusTypeUpdateInput(
        libelle=payload.libelle,
        type=type_val,
        montant=payload.montant,
        seuil_heures=payload.seuil_heures,
        soumise_a_cotisations=payload.soumise_a_cotisations,
        soumise_a_impot=payload.soumise_a_impot,
        prompt_ia=payload.prompt_ia,
    )
