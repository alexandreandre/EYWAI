"""Choix mutuelle par le salarié (self-service onboarding)."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from app.core.database import supabase
from app.modules.mutuelle_types.domain.employee_choice import (
    is_mutuelle_eligible_for_employee,
    resolve_organisme_label,
)
from app.modules.mutuelle_types.infrastructure.repository import (
    SupabaseMutuelleTypeRepository,
)


def _get_psc_settings(company_id: str) -> dict[str, Any]:
    resp = (
        supabase.table("company_psc_settings")
        .select("*")
        .eq("company_id", company_id)
        .limit(1)
        .execute()
    )
    if resp.data:
        return resp.data[0]
    return {
        "company_id": company_id,
        "mutuelle_organisme_label": None,
        "mutuelle_employee_self_service": False,
    }


def get_employee_mutuelle_choices(
    company_id: str,
    employee_id: str,
) -> dict[str, Any]:
    """Options mutuelle éligibles + sélection courante pour un salarié."""
    emp_resp = (
        supabase.table("employees")
        .select("id, statut, specificites_paie")
        .eq("id", employee_id)
        .eq("company_id", company_id)
        .limit(1)
        .execute()
    )
    if not emp_resp.data:
        raise HTTPException(status_code=404, detail="Employé non trouvé.")
    employee = emp_resp.data[0]
    psc = _get_psc_settings(company_id)
    repo = SupabaseMutuelleTypeRepository(supabase)
    catalog = repo.list_by_company(company_id)
    eligible = [
        m
        for m in catalog
        if is_mutuelle_eligible_for_employee(
            {
                "is_active": m.is_active,
                "statut_categoriel": m.statut_categoriel,
            },
            employee.get("statut"),
        )
    ]
    spec = employee.get("specificites_paie") or {}
    mutuelle_spec = spec.get("mutuelle") or {}
    current_ids = mutuelle_spec.get("mutuelle_type_ids") or []
    current_id = str(current_ids[0]) if current_ids else None
    company_label = psc.get("mutuelle_organisme_label")
    options = []
    for entity in eligible:
        row = {
            "id": str(entity.id),
            "libelle": entity.libelle,
            "montant_salarial": entity.montant_salarial,
            "montant_patronal": entity.montant_patronal,
            "pack_couverture": entity.pack_couverture,
            "statut_categoriel": entity.statut_categoriel,
            "organisme_label": entity.organisme_label,
            "note": entity.note,
            "code_option_dsn": entity.code_option_dsn,
        }
        row["organisme_display"] = resolve_organisme_label(row, company_label)
        options.append(row)
    options.sort(
        key=lambda o: (
            {"isole": 0, "duo": 1, "famille": 2, "autre": 3}.get(
                o.get("pack_couverture") or "", 4
            ),
            o.get("montant_salarial") or 0,
        )
    )
    return {
        "organisme_label": company_label,
        "self_service_enabled": bool(psc.get("mutuelle_employee_self_service", False)),
        "current_mutuelle_type_id": current_id,
        "options": options,
    }


def assign_employee_mutuelle_choice(
    company_id: str,
    employee_id: str,
    mutuelle_type_id: str,
    actor_user_id: str,
    *,
    allow_rh_override: bool = False,
) -> dict[str, Any]:
    """Affecte une formule mutuelle unique au salarié."""
    psc = _get_psc_settings(company_id)
    if not allow_rh_override and not psc.get("mutuelle_employee_self_service", False):
        raise HTTPException(
            status_code=403,
            detail="Le choix mutuelle par le salarié est désactivé pour cette entreprise.",
        )
    emp_resp = (
        supabase.table("employees")
        .select("id, statut")
        .eq("id", employee_id)
        .eq("company_id", company_id)
        .limit(1)
        .execute()
    )
    if not emp_resp.data:
        raise HTTPException(status_code=404, detail="Employé non trouvé.")
    employee = emp_resp.data[0]
    repo = SupabaseMutuelleTypeRepository(supabase)
    mutuelle = repo.get_by_id(mutuelle_type_id, company_id)
    if mutuelle is None:
        raise HTTPException(status_code=404, detail="Formule mutuelle non trouvée.")
    if not is_mutuelle_eligible_for_employee(
        {
            "is_active": mutuelle.is_active,
            "statut_categoriel": mutuelle.statut_categoriel,
        },
        employee.get("statut"),
    ):
        raise HTTPException(
            status_code=400,
            detail="Cette formule mutuelle n'est pas compatible avec votre statut.",
        )
    repo.replace_employee_mutuelle(employee_id, mutuelle_type_id, actor_user_id)
    return get_employee_mutuelle_choices(company_id, employee_id)
