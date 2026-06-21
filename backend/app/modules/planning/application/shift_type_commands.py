"""Commandes CRUD types de poste planning."""

from __future__ import annotations

from typing import Any

from app.modules.planning.infrastructure.repository import planning_repository


def list_shift_types_for_company(company_id: str) -> list[dict[str, Any]]:
    from app.modules.planning.application import queries as app_queries

    return app_queries.get_shift_types_for_company(company_id)


def create_shift_type(
    company_id: str,
    data: dict[str, Any],
) -> dict[str, Any]:
    settings = planning_repository.get_company_planning_settings(company_id)
    cc_id = (settings or {}).get("collective_agreement_id")
    if not cc_id:
        raise ValueError(
            "Configurez d'abord la convention collective planning de l'entreprise."
        )
    payload = {
        **data,
        "collective_agreement_id": cc_id,
        "is_active": data.get("is_active", True),
    }
    return planning_repository.create_shift_type(payload)


def update_shift_type(
    company_id: str,
    shift_type_id: str,
    data: dict[str, Any],
) -> dict[str, Any]:
    existing = planning_repository.get_shift_type_by_id(shift_type_id)
    if not existing:
        raise LookupError("Type de poste introuvable.")
    settings = planning_repository.get_company_planning_settings(company_id)
    cc_id = (settings or {}).get("collective_agreement_id")
    if cc_id and str(existing.get("collective_agreement_id")) != str(cc_id):
        raise PermissionError("Ce type de poste n'appartient pas à la CC de l'entreprise.")
    return planning_repository.update_shift_type(shift_type_id, data)


def delete_shift_type(company_id: str, shift_type_id: str) -> None:
    existing = planning_repository.get_shift_type_by_id(shift_type_id)
    if not existing:
        raise LookupError("Type de poste introuvable.")
    settings = planning_repository.get_company_planning_settings(company_id)
    cc_id = (settings or {}).get("collective_agreement_id")
    if cc_id and str(existing.get("collective_agreement_id")) != str(cc_id):
        raise PermissionError("Ce type de poste n'appartient pas à la CC de l'entreprise.")
    planning_repository.deactivate_shift_type(shift_type_id)
