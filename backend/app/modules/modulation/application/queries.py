"""Queries modulation."""

from __future__ import annotations

import unicodedata
from datetime import date

from app.core.database import supabase
from app.modules.modulation.domain.entities import ModulationSettings
from app.modules.modulation.domain.hour_account_rules import solde_au
from app.modules.modulation.infrastructure import repository as repo
from app.modules.modulation.schemas.requests import (
    ModulationOverviewRow,
    ModulationSettingsResponse,
    WeekTemplateSchema,
)


def _settings_to_response(
    company_id: str, settings: ModulationSettings
) -> ModulationSettingsResponse:
    row = repo.get_modulation_settings_row(company_id)
    return ModulationSettingsResponse(
        company_id=company_id,
        enabled=settings.enabled,
        configured=row is not None,
        reference_period_months=settings.reference_period_months,
        average_weekly_hours=settings.average_weekly_hours,
        weekly_high_hours=settings.weekly_high_hours,
        weekly_low_hours=settings.weekly_low_hours,
        high_weeks_per_cycle=settings.high_weeks_per_cycle,
        low_weeks_per_cycle=settings.low_weeks_per_cycle,
        cycle_start_week_iso=settings.cycle_start_week_iso,
        pay_smoothed=settings.pay_smoothed,
        weekly_cap_hours=settings.weekly_cap_hours,
        theoretical_annual_hours=settings.theoretical_annual_hours,
        hour_account_enabled=settings.hour_account_enabled,
        hs_franchise_hours_per_period=settings.hs_franchise_hours_per_period,
        hs_franchise_period=settings.hs_franchise_period,
        max_account_balance_hours=settings.max_account_balance_hours,
        account_credit_source=settings.account_credit_source,
        recovery_absence_enabled=settings.recovery_absence_enabled,
        recovery_debit_timing=settings.recovery_debit_timing,
        hs_routing_policy=settings.hs_routing_policy,
        **_salaries_a_regle_propre(company_id, settings),
    )


def _salaries_a_regle_propre(company_id: str, settings: ModulationSettings) -> dict[str, int]:
    """Les salariés présents qui suivent leur propre règle ; sans compteur, la
    règle n'a pas d'effet et rien n'est compté."""
    if not settings.hour_account_enabled:
        return {"salaries_regle_propre": 0, "salaries_toujours_au_compteur": 0}
    regles = repo.list_hs_routing_overrides(company_id, sans_partis=True)
    return {
        "salaries_regle_propre": len(regles),
        "salaries_toujours_au_compteur": sum(1 for r in regles.values() if r == "account_all"),
    }


def regle_heures_sup_du_salarie(company_id: str, employee_id: str) -> dict:
    """Ce que la fiche du salarié montre : sa règle propre (None : celle de la
    société), la règle de la société, et si la société a un compteur."""
    settings = repo.get_modulation_settings(company_id)
    return {
        "regle": repo.get_hs_routing_override(employee_id),
        "regle_societe": settings.hs_routing_policy,
        "compteur_ouvert": settings.hour_account_enabled,
    }


def get_modulation_settings(company_id: str) -> ModulationSettingsResponse:
    settings = repo.get_modulation_settings(company_id)
    return _settings_to_response(company_id, settings)


def list_week_templates(company_id: str) -> list[WeekTemplateSchema]:
    templates = repo.list_week_templates(company_id)
    return [
        WeekTemplateSchema(
            id=t.id,
            name=t.name,
            weekly_hours=t.weekly_hours,
            day_configs=t.day_configs,
            modulation_tier=t.modulation_tier,
            is_active=t.is_active,
            team_id=t.team_id,
            description=t.description,
        )
        for t in templates
    ]


def _cle_de_tri(texte: str) -> str:
    """« Écuyer » avant « Zola » : sans accents ni casse."""
    return "".join(
        c for c in unicodedata.normalize("NFD", texte or "") if unicodedata.category(c) != "Mn"
    ).lower()


def get_modulation_overview(
    company_id: str, year: int | None = None
) -> list[ModulationOverviewRow]:
    ref_year = year or date.today().year
    counters = repo.list_employee_counters(company_id, ref_year)
    # Tous les salariés actifs, avec ou sans compteur : dès qu'un seul salarié
    # avait un compteur, les autres disparaissaient de la liste (LEWIS, 26/11).
    emp_resp = (
        supabase.table("employees")
        .select("id, first_name, last_name, duree_hebdomadaire")
        .eq("company_id", company_id)
        .in_("employment_status", ["actif", "active"])
        .execute()
    )
    settings = repo.get_modulation_settings(company_id)
    rows: list[ModulationOverviewRow] = []
    vus: set[str] = set()
    for c in counters:
        emp = c.get("employees") or {}
        vus.add(str(c["employee_id"]))
        rows.append(
            ModulationOverviewRow(
                employee_id=str(c["employee_id"]),
                first_name=emp.get("first_name") or "",
                last_name=emp.get("last_name") or "",
                theoretical_hours=float(c.get("theoretical_hours") or 0),
                actual_hours=float(c.get("actual_hours") or 0),
                balance_hours=float(c.get("balance_hours") or 0),
                account_balance_hours=float(c.get("account_balance_hours") or 0),
                period_credited_hours=float(c.get("period_credited_hours") or 0),
                period_paid_hours=float(c.get("period_paid_hours") or 0),
            )
        )
    sans_compteur = [str(e["id"]) for e in emp_resp.data or [] if str(e["id"]) not in vus]
    mouvements: dict[str, list[dict]] = {}
    for m in repo.list_movements_for_employees(sans_compteur):
        mouvements.setdefault(str(m.get("employee_id")), []).append(m)
    for emp in emp_resp.data or []:
        if str(emp["id"]) in vus:
            continue
        leurs = mouvements.get(str(emp["id"]), [])
        weekly = float(emp.get("duree_hebdomadaire") or settings.average_weekly_hours)
        theoretical = round(weekly * 52, 2)
        rows.append(
            ModulationOverviewRow(
                employee_id=str(emp["id"]),
                first_name=emp.get("first_name") or "",
                last_name=emp.get("last_name") or "",
                theoretical_hours=theoretical,
                actual_hours=theoretical,
                balance_hours=0.0,
                # Pas encore de ligne pour l'année : le solde d'avant se reporte
                # (repos non pris = dû), il ne repart pas de zéro au 1er janvier.
                account_balance_hours=solde_au(leurs, ref_year, 12),
                has_movements=bool(leurs),
                estimated=True,
            )
        )
    rows.sort(key=lambda r: (_cle_de_tri(r.last_name), _cle_de_tri(r.first_name)))
    return rows
