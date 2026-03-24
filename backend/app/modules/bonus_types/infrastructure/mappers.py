"""
Mappers dict/row Supabase <-> entités domaine BonusType.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from app.modules.bonus_types.domain.entities import BonusType
from app.modules.bonus_types.domain.enums import BonusTypeKind


def _parse_uuid(v: Any) -> UUID | None:
    if v is None:
        return None
    if isinstance(v, UUID):
        return v
    return UUID(str(v))


def _parse_datetime(v: Any) -> datetime | None:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v
    if isinstance(v, str):
        return datetime.fromisoformat(v.replace("Z", "+00:00"))
    return None


def _parse_kind(v: Any) -> BonusTypeKind:
    if isinstance(v, BonusTypeKind):
        return v
    return BonusTypeKind(str(v)) if v else BonusTypeKind.MONTANT_FIXE


def row_to_bonus_type(row: dict[str, Any]) -> BonusType:
    """Convertit une ligne Supabase (company_bonus_types) en BonusType."""
    return BonusType(
        id=_parse_uuid(row.get("id")),
        company_id=_parse_uuid(row["company_id"]) or UUID(int=0),
        libelle=str(row.get("libelle", "")),
        type=_parse_kind(row.get("type")),
        montant=float(row.get("montant", 0)),
        seuil_heures=float(row["seuil_heures"]) if row.get("seuil_heures") is not None else None,
        soumise_a_cotisations=bool(row.get("soumise_a_cotisations", True)),
        soumise_a_impot=bool(row.get("soumise_a_impot", True)),
        prompt_ia=row.get("prompt_ia"),
        created_at=_parse_datetime(row.get("created_at")),
        updated_at=_parse_datetime(row.get("updated_at")),
        created_by=_parse_uuid(row.get("created_by")),
    )


def bonus_type_to_row(entity: BonusType) -> dict[str, Any]:
    """Convertit un BonusType en dict pour insert Supabase."""
    row: dict[str, Any] = {
        "company_id": str(entity.company_id),
        "libelle": entity.libelle,
        "type": entity.type.value,
        "montant": entity.montant,
        "seuil_heures": entity.seuil_heures,
        "soumise_a_cotisations": entity.soumise_a_cotisations,
        "soumise_a_impot": entity.soumise_a_impot,
        "prompt_ia": entity.prompt_ia,
    }
    if entity.created_by is not None:
        row["created_by"] = str(entity.created_by)
    return row


def entity_to_api_dict(entity: BonusType) -> dict[str, Any]:
    """Convertit une entité BonusType en dict pour réponse API (même forme que legacy).
    Pour les réponses HTTP, préférer application.dto.bonus_type_to_response_dict."""
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
