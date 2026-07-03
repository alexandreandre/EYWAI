"""
Application d'un preset 2026 : matérialise les modèles + plans déclaratifs en
enregistrements éditables (company_week_schedule_templates + company_schedule_plans).

Les modèles/plans créés restent entièrement modifiables par les RH ; rien n'est
figé côté paie. Les affectations salarié non résolues déclenchent une alerte RH
(`needs_confirmation`) plutôt qu'une hypothèse figée.
"""
from __future__ import annotations

from typing import Any, Dict, List

from app.modules.modulation.infrastructure import repository as mod_repo
from app.modules.schedules.application.presets_2026 import get_registry
from app.modules.schedules.domain.calendar_generation_rules import week_weekly_hours
from app.modules.schedules.infrastructure import schedule_plans_repository as plans_repo


def apply_preset(company_id: str, preset_key: str) -> Dict[str, Any]:
    registry = get_registry()
    preset = registry.get(preset_key)
    if preset is None:
        raise ValueError(f"Preset inconnu : {preset_key}")

    # 1) Modèles de semaine (upsert par nom pour rester idempotent / éditable).
    template_ids: Dict[str, str] = {}
    for spec in preset.templates:
        payload = {
            "name": spec.name,
            "description": spec.description,
            "weekly_hours": week_weekly_hours(spec.days),
            "day_configs": spec.days,
            "modulation_tier": spec.modulation_tier,
            "is_active": True,
        }
        existing = plans_repo.find_template_by_name(company_id, spec.name)
        row = mod_repo.upsert_week_template(
            company_id, payload, template_id=str(existing["id"]) if existing else None
        )
        template_ids[spec.name] = str(row.get("id"))

    # 2) Plans / affectations.
    created_plans: List[Dict[str, Any]] = []
    # Résolution best-effort des salariés nommés dans le preset.
    all_names = sorted(
        {n for p in preset.plans for n in p.employee_names}
    )
    name_to_id = plans_repo.find_employees_by_name(company_id, all_names) if all_names else {}

    for p in preset.plans:
        cycle = [template_ids[name] for name in p.template_names if name in template_ids]
        resolved_ids = [name_to_id[n] for n in p.employee_names if n in name_to_id]
        unresolved = [n for n in p.employee_names if n not in name_to_id]

        scope_type = p.scope_type
        scope_ref: Dict[str, Any] = {}
        if scope_type == "employees":
            scope_ref = {"employee_ids": resolved_ids}

        needs_confirmation = bool(p.needs_confirmation or unresolved)
        notes = p.notes
        if unresolved:
            notes = (notes + " " if notes else "") + (
                f"Affectation à confirmer : {', '.join(unresolved)} introuvable(s)."
            )

        plan_payload = {
            "name": p.name,
            "scope_type": scope_type,
            "scope_ref": scope_ref,
            "template_cycle": cycle,
            "cycle_anchor": p.cycle_anchor,
            "start_date": p.start_date,
            "end_date": p.end_date,
            "overwrite_mode": p.overwrite_mode,
            "needs_confirmation": needs_confirmation,
            "notes": notes,
            "is_active": True,
        }
        # Idempotent : ré-appliquer un preset met à jour le plan existant (par nom)
        # au lieu de le dupliquer. Le statut n'est pas réécrit s'il est déjà appliqué.
        existing_plan = plans_repo.find_plan_by_name(company_id, p.name)
        if existing_plan:
            row = plans_repo.update_plan(company_id, str(existing_plan["id"]), plan_payload)
        else:
            row = plans_repo.create_plan(company_id, {**plan_payload, "status": "draft"})
        created_plans.append(row)

    return {
        "status": "success",
        "preset": preset.key,
        "company_label": preset.company_label,
        "templates_created": len(template_ids),
        "plans_created": len(created_plans),
        "plans": created_plans,
    }


__all__ = ["apply_preset"]
