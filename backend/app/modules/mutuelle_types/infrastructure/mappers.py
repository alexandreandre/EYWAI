"""
Mappers entre modèles persistance (dict/row Supabase) et entités domain.

Pas de FastAPI ; conversions pures.
"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.modules.mutuelle_types.domain.entities import MutuelleType


def _parse_uuid(value: str | UUID | None) -> UUID | None:
    if value is None:
        return None
    if isinstance(value, UUID):
        return value
    return UUID(str(value))


def _parse_datetime(value: datetime | str | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    return None


def row_to_mutuelle_type(row: dict) -> MutuelleType:
    """Convertit une ligne Supabase (company_mutuelle_types) en entité domain."""
    return MutuelleType(
        id=_parse_uuid(row.get("id")),
        company_id=_parse_uuid(row["company_id"]) or UUID(int=0),
        libelle=row["libelle"],
        montant_salarial=float(row.get("montant_salarial", 0)),
        montant_patronal=float(row.get("montant_patronal", 0)),
        part_patronale_soumise_a_csg=bool(
            row.get("part_patronale_soumise_a_csg", True)
        ),
        is_active=bool(row.get("is_active", True)),
        created_at=_parse_datetime(row.get("created_at")),
        updated_at=_parse_datetime(row.get("updated_at")),
        created_by=_parse_uuid(row.get("created_by")),
    )


def mutuelle_type_to_row(entity: MutuelleType) -> dict:
    """Convertit une entité en dict pour insert/update Supabase (sans id si create)."""
    row: dict = {
        "company_id": str(entity.company_id),
        "libelle": entity.libelle,
        "montant_salarial": entity.montant_salarial,
        "montant_patronal": entity.montant_patronal,
        "part_patronale_soumise_a_csg": entity.part_patronale_soumise_a_csg,
        "is_active": entity.is_active,
    }
    if entity.id is not None:
        row["id"] = str(entity.id)
    if entity.created_at is not None:
        row["created_at"] = entity.created_at.isoformat()
    if entity.updated_at is not None:
        row["updated_at"] = entity.updated_at.isoformat()
    if entity.created_by is not None:
        row["created_by"] = str(entity.created_by)
    return row


def entity_to_response_dict(
    entity: MutuelleType, employee_ids: list[str]
) -> dict:
    """Construit le dict de réponse API (formule + employee_ids). Pas de FastAPI."""
    return {
        "id": str(entity.id) if entity.id else None,
        "company_id": str(entity.company_id),
        "libelle": entity.libelle,
        "montant_salarial": entity.montant_salarial,
        "montant_patronal": entity.montant_patronal,
        "part_patronale_soumise_a_csg": entity.part_patronale_soumise_a_csg,
        "is_active": entity.is_active,
        "created_at": (
            entity.created_at.isoformat() if entity.created_at else None
        ),
        "updated_at": (
            entity.updated_at.isoformat() if entity.updated_at else None
        ),
        "created_by": str(entity.created_by) if entity.created_by else None,
        "employee_ids": employee_ids,
    }
