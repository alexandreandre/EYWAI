"""
Service de génération des calendriers prévisionnels.

Prend un plan (ou une spécification inline), résout les modèles du cycle, les
salariés de la portée, les jours fériés et le statut forfait, puis remplit
`employee_schedules.planned_calendar.calendrier_prevu` mois par mois. Supporte
l'alternance de semaines, les modes overwrite / preserve_manual / fill_empty, un
mode dry-run (aperçu sans écriture) et un recalcul paie optionnel.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from app.core.logging import get_logger
from app.modules.schedules.domain import rules as domain_rules
from app.modules.schedules.domain.calendar_generation_rules import (
    OVERWRITE_ALL,
    OVERWRITE_MODES,
    build_month_calendrier_prevu,
    day_config_map,
    resolve_cycle_week_index,
    weekly_totals_from_entries,
)
from app.modules.schedules.infrastructure import schedule_plans_repository as plans_repo
from app.modules.schedules.infrastructure.mappers import (
    extract_calendrier_prevu_from_planned_calendar,
)
from app.modules.schedules.infrastructure.repository import schedule_repository
from app.shared.public_holidays import day_numbers_observed_holidays

logger = get_logger("modules.schedules.application.calendar_generation")


@dataclass
class GenerationSpec:
    """Spécification résolue d'une génération (issue d'un plan ou inline)."""

    company_id: str
    template_cycle: List[str]
    start_date: date
    end_date: date
    cycle_anchor: date
    overwrite_mode: str = OVERWRITE_ALL
    plan_id: Optional[str] = None
    employee_ids: Optional[List[str]] = None       # override explicite
    scope_type: str = "company"
    scope_ref: Dict[str, Any] = field(default_factory=dict)


def _parse_date(value: Any, default: date) -> date:
    if value is None or value == "":
        return default
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _months_in_range(start: date, end: date) -> List[tuple[int, int]]:
    out: List[tuple[int, int]] = []
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        out.append((y, m))
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return out


def spec_from_plan(
    plan: Dict[str, Any],
    *,
    year: Optional[int] = None,
    overwrite_mode: Optional[str] = None,
) -> GenerationSpec:
    start = _parse_date(plan.get("start_date"), date(year or date.today().year, 1, 1))
    end = _parse_date(plan.get("end_date"), date(start.year, 12, 31))
    if year is not None:
        # Restreint la génération à l'année demandée.
        start = max(start, date(year, 1, 1))
        end = min(end, date(year, 12, 31))
    anchor = _parse_date(plan.get("cycle_anchor"), start)
    mode = overwrite_mode or plan.get("overwrite_mode") or OVERWRITE_ALL
    if mode not in OVERWRITE_MODES:
        mode = OVERWRITE_ALL
    return GenerationSpec(
        company_id=str(plan["company_id"]),
        template_cycle=[str(t) for t in (plan.get("template_cycle") or [])],
        start_date=start,
        end_date=end,
        cycle_anchor=anchor,
        overwrite_mode=mode,
        plan_id=str(plan.get("id")) if plan.get("id") else None,
        scope_type=plan.get("scope_type") or "company",
        scope_ref=plan.get("scope_ref") or {},
    )


def generate(
    spec: GenerationSpec,
    *,
    dry_run: bool = False,
    recalculate_payroll: bool = False,
) -> Dict[str, Any]:
    """Exécute la génération et renvoie un résumé (ou un aperçu si dry_run)."""
    if not spec.template_cycle:
        return {
            "status": "skipped",
            "reason": "Aucun modèle dans le cycle (plan informatif / forfaitaire).",
            "employees": [],
        }

    templates = plans_repo.get_templates_by_ids(spec.company_id, spec.template_cycle)
    missing = [tid for tid in spec.template_cycle if tid not in templates]
    if missing:
        raise ValueError(f"Modèle(s) introuvable(s) : {missing}")

    # Cartes jour ISO → config, dans l'ordre du cycle.
    cycle_maps = [day_config_map(templates[tid].get("day_configs") or []) for tid in spec.template_cycle]
    cycle_ids = list(spec.template_cycle)
    cycle_len = len(cycle_ids)

    def resolve_week_day_map(monday: date) -> Dict[int, Dict[str, Any]]:
        idx = resolve_cycle_week_index(cycle_len, spec.cycle_anchor, monday)
        return cycle_maps[idx]

    def template_id_for_week(monday: date) -> str:
        idx = resolve_cycle_week_index(cycle_len, spec.cycle_anchor, monday)
        return cycle_ids[idx]

    def day_in_range(d: date) -> bool:
        return spec.start_date <= d <= spec.end_date

    # Résolution des salariés.
    if spec.employee_ids is not None:
        employees = plans_repo.resolve_scope_employees(
            spec.company_id, "employees", {"employee_ids": spec.employee_ids}
        )
    else:
        employees = plans_repo.resolve_scope_employees(
            spec.company_id, spec.scope_type, spec.scope_ref
        )

    months = _months_in_range(spec.start_date, spec.end_date)
    generated_at = datetime.now(timezone.utc).isoformat()
    emp_summaries: List[Dict[str, Any]] = []

    # Jours fériés observés : calculés une fois par mois (partagés entre salariés).
    holidays_cache: Dict[tuple[int, int], set[int]] = {}
    for (year, month) in months:
        holidays_cache[(year, month)] = day_numbers_observed_holidays(
            year, month, spec.company_id
        )

    # Écritures accumulées puis envoyées en lot (bien plus rapide que 1 appel/mois).
    write_payloads: List[Dict[str, Any]] = []
    recalc_targets: List[tuple[str, int, int]] = []

    for emp in employees:
        employee_id = str(emp["id"])
        is_forfait = domain_rules.is_forfait_jour(emp.get("statut"))
        months_summary: List[Dict[str, Any]] = []

        # Une seule lecture des calendriers existants pour toute la plage.
        existing_map: Dict[tuple[int, int], List[Dict[str, Any]]] = {}
        for row in schedule_repository.get_schedules_for_months(employee_id, months):
            key = (row.get("year"), row.get("month"))
            existing_map[key] = extract_calendrier_prevu_from_planned_calendar(
                row.get("planned_calendar")
            )

        for (year, month) in months:
            existing_entries = existing_map.get((year, month), [])
            entries = build_month_calendrier_prevu(
                year,
                month,
                resolve_week_day_map,
                holidays=holidays_cache.get((year, month), set()),
                is_forfait=is_forfait,
                existing_entries=existing_entries,
                overwrite_mode=spec.overwrite_mode,
                template_id_for_week=template_id_for_week,
                day_in_range=day_in_range,
            )

            planned_calendar_json = {
                "periode": {"mois": month, "annee": year},
                "source": {
                    "plan_id": spec.plan_id,
                    "template_ids": cycle_ids,
                    "applied_mode": spec.overwrite_mode,
                    "generated_at": generated_at,
                },
                "calendrier_prevu": entries,
            }

            if not dry_run:
                write_payloads.append(
                    {
                        "employee_id": employee_id,
                        "company_id": spec.company_id,
                        "year": year,
                        "month": month,
                        "planned_calendar": planned_calendar_json,
                    }
                )
                if recalculate_payroll:
                    recalc_targets.append((employee_id, year, month))

            months_summary.append(
                {
                    "year": year,
                    "month": month,
                    "weekly_totals": weekly_totals_from_entries(entries, year, month),
                    "days": len(entries),
                }
            )

        emp_summaries.append(
            {
                "employee_id": employee_id,
                "name": f"{emp.get('first_name') or ''} {emp.get('last_name') or ''}".strip(),
                "is_forfait": is_forfait,
                "months": months_summary,
            }
        )

    if not dry_run and write_payloads:
        schedule_repository.bulk_upsert_schedules(write_payloads)
        for (employee_id, year, month) in recalc_targets:
            _safe_recalculate_payroll(employee_id, year, month)

    return {
        "status": "preview" if dry_run else "applied",
        "dry_run": dry_run,
        "plan_id": spec.plan_id,
        "overwrite_mode": spec.overwrite_mode,
        "start_date": spec.start_date.isoformat(),
        "end_date": spec.end_date.isoformat(),
        "employee_count": len(employees),
        "employees": emp_summaries,
    }


def generate_from_plan(
    company_id: str,
    plan_id: str,
    *,
    year: Optional[int] = None,
    overwrite_mode: Optional[str] = None,
    dry_run: bool = False,
    recalculate_payroll: bool = False,
) -> Dict[str, Any]:
    plan = plans_repo.get_plan(company_id, plan_id)
    if not plan:
        raise ValueError(f"Plan {plan_id} introuvable")
    spec = spec_from_plan(plan, year=year, overwrite_mode=overwrite_mode)
    result = generate(spec, dry_run=dry_run, recalculate_payroll=recalculate_payroll)
    if not dry_run and result.get("status") == "applied":
        plans_repo.update_plan(company_id, plan_id, {"status": "applied"})
    return result


# Précédence de portée : le plus spécifique passe EN DERNIER pour écraser le plus
# large (ex. l'exception salarié Rina/Sihem écrase le modèle société MBC).
_SCOPE_ORDER = {"company": 0, "team": 1, "service": 2, "employees": 3}


def generate_all_active_plans(
    company_id: str,
    *,
    year: Optional[int] = None,
    dry_run: bool = False,
    recalculate_payroll: bool = False,
    on_plan_done: Optional[Callable[[Dict[str, Any]], None]] = None,
) -> Dict[str, Any]:
    """Génère (ou prévisualise) tous les plans actifs d'une société, dans l'ordre
    de précédence pour que les exceptions salarié priment sur les modèles société.

    `on_plan_done` est appelé après chaque plan (progression / streaming CLI).
    """
    plans = plans_repo.list_plans(company_id, active_only=True)
    plans_sorted = sorted(
        plans,
        key=lambda p: (
            _SCOPE_ORDER.get(p.get("scope_type") or "company", 0),
            p.get("start_date") or "",
        ),
    )
    plan_results: List[Dict[str, Any]] = []
    total_employees = 0
    for plan in plans_sorted:
        spec = spec_from_plan(plan, year=year)
        result = generate(spec, dry_run=dry_run, recalculate_payroll=recalculate_payroll)
        if not dry_run and result.get("status") == "applied":
            plans_repo.update_plan(company_id, str(plan["id"]), {"status": "applied"})
        total_employees += result.get("employee_count") or 0
        summary = {
            "plan_id": str(plan.get("id")),
            "plan_name": plan.get("name"),
            "scope_type": plan.get("scope_type"),
            "status": result.get("status"),
            "employee_count": result.get("employee_count", 0),
            "reason": result.get("reason"),
        }
        plan_results.append(summary)
        if on_plan_done is not None:
            on_plan_done(summary)
    return {
        "status": "preview" if dry_run else "applied",
        "company_id": company_id,
        "plans_processed": len(plan_results),
        "employee_writes": total_employees,
        "plans": plan_results,
    }


def _safe_recalculate_payroll(employee_id: str, year: int, month: int) -> None:
    """Recalcul paie best-effort — ne bloque jamais la génération."""
    try:
        from app.modules.schedules.application.commands import calculate_payroll_events

        calculate_payroll_events(employee_id, year, month)
    except Exception as e:  # pragma: no cover - défensif
        logger.warning("Recalcul paie ignoré (%s/%s) : %s", month, year, e)


__all__ = [
    "GenerationSpec",
    "generate",
    "generate_from_plan",
    "generate_all_active_plans",
    "spec_from_plan",
]
