"""
Mappers entre modèles persistance (Supabase) et entités du domaine.

participation_simulations (row) <-> ParticipationSimulation (entity).
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict
from uuid import UUID

from app.modules.participation.domain.entities import ParticipationSimulation
from app.modules.participation.domain.enums import DistributionMode


def _parse_uuid(value: Any) -> UUID:
    if value is None:
        raise ValueError("UUID cannot be None")
    return UUID(str(value)) if not isinstance(value, UUID) else value


def _parse_optional_uuid(value: Any) -> UUID | None:
    if value is None:
        return None
    return UUID(str(value)) if not isinstance(value, UUID) else value


def _parse_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if value is None:
        raise ValueError("datetime cannot be None")
    if isinstance(value, str):
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    raise TypeError(f"Cannot parse datetime from {type(value)}")


def row_to_participation_simulation(row: Dict[str, Any]) -> ParticipationSimulation:
    """Convertit une ligne Supabase en entité ParticipationSimulation."""
    participation_mode = row.get("participation_mode")
    interessement_mode = row.get("interessement_mode")
    return ParticipationSimulation(
        id=_parse_uuid(row["id"]),
        company_id=_parse_uuid(row["company_id"]),
        year=int(row["year"]),
        simulation_name=str(row["simulation_name"]),
        benefice_net=float(row["benefice_net"]),
        capitaux_propres=float(row["capitaux_propres"]),
        salaires_bruts=float(row["salaires_bruts"]),
        valeur_ajoutee=float(row["valeur_ajoutee"]),
        participation_mode=DistributionMode(participation_mode)
        if isinstance(participation_mode, str)
        else participation_mode,
        participation_salaire_percent=int(row["participation_salaire_percent"]),
        participation_presence_percent=int(row["participation_presence_percent"]),
        interessement_enabled=bool(row["interessement_enabled"]),
        interessement_envelope=float(row["interessement_envelope"])
        if row.get("interessement_envelope") is not None
        else None,
        interessement_mode=DistributionMode(interessement_mode)
        if interessement_mode
        else None,
        interessement_salaire_percent=int(row["interessement_salaire_percent"]),
        interessement_presence_percent=int(row["interessement_presence_percent"]),
        results_data=dict(row["results_data"]) if row.get("results_data") else {},
        created_at=_parse_datetime(row["created_at"]),
        created_by=_parse_optional_uuid(row.get("created_by")),
        updated_at=_parse_datetime(row["updated_at"]),
    )


def participation_simulation_to_row(
    entity: ParticipationSimulation,
) -> Dict[str, Any]:
    """Convertit une entité en dict pour insert/update Supabase."""
    return {
        "id": str(entity.id),
        "company_id": str(entity.company_id),
        "year": entity.year,
        "simulation_name": entity.simulation_name,
        "benefice_net": entity.benefice_net,
        "capitaux_propres": entity.capitaux_propres,
        "salaires_bruts": entity.salaires_bruts,
        "valeur_ajoutee": entity.valeur_ajoutee,
        "participation_mode": entity.participation_mode.value
        if hasattr(entity.participation_mode, "value")
        else entity.participation_mode,
        "participation_salaire_percent": entity.participation_salaire_percent,
        "participation_presence_percent": entity.participation_presence_percent,
        "interessement_enabled": entity.interessement_enabled,
        "interessement_envelope": entity.interessement_envelope,
        "interessement_mode": entity.interessement_mode.value
        if entity.interessement_mode and hasattr(entity.interessement_mode, "value")
        else entity.interessement_mode,
        "interessement_salaire_percent": entity.interessement_salaire_percent,
        "interessement_presence_percent": entity.interessement_presence_percent,
        "results_data": entity.results_data,
        "created_at": entity.created_at.isoformat(),
        "created_by": str(entity.created_by) if entity.created_by else None,
        "updated_at": entity.updated_at.isoformat(),
    }
