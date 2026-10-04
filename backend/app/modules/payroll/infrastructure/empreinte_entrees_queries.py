"""Lectures groupées pour l'empreinte d'entrée d'un bulletin.

Une passe par salarié : fiche, société, calendriers de la fenêtre, absences
validées, saisies des mois demandés, notes de frais de la plage. Pas une
requête par bulletin.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from app.core.database import supabase
from app.modules.payroll.domain.empreinte_entrees import mois_de_la_fenetre

FICHE_COLONNES = (
    "id, company_id, salaire_de_base, classification_conventionnelle, "
    "duree_hebdomadaire, is_temps_partiel, statut, is_forfait_jour, hire_date, "
    "seniority_reference_date, prior_service_months, contract_end_date, "
    "contract_type, elements_variables, avantages_en_nature, specificites_paie, "
    "job_title, date_conclusion_contrat, date_debut_execution, current_exit_id"
)

SAISIE_COLONNES = (
    "year, month, name, amount, catalog_prime_id, is_socially_taxed, is_taxable, "
    "payroll_quantity, sur_le_net, export_code, quantity_kind, situation_repas, "
    "description, participation_campaign_id, participation_bulletin_id"
)

SOCIETE_COLONNES = (
    "id, idcc, effectif, taux_at_mp, taux_vm, taux_fnal, "
    "paie_jour_de_fin, paie_occurrence, settings"
)


@dataclass(frozen=True)
class LecturesEmpreinte:
    employee: dict[str, Any]
    company: dict[str, Any]
    calendriers: dict[tuple[int, int], dict[str, Any]]
    absences: list[dict[str, Any]]
    saisies_par_mois: dict[tuple[int, int], list[dict[str, Any]]]
    notes_de_frais: list[dict[str, Any]]
    surcharges_fenetre: dict[tuple[int, int], date] = field(default_factory=dict)


def _mois_a_lire(periodes: list[tuple[int, int]]) -> list[tuple[int, int]]:
    vus: set[tuple[int, int]] = set()
    for year, month in periodes:
        vus.update(mois_de_la_fenetre(year, month))
    return sorted(vus)


def _plage_dates(mois: list[tuple[int, int]]) -> tuple[str, str] | None:
    if not mois:
        return None
    premier, dernier = mois[0], mois[-1]
    debut = date(premier[0], premier[1], 1)
    fin = date(dernier[0], dernier[1], calendar.monthrange(dernier[0], dernier[1])[1])
    return debut.isoformat(), fin.isoformat()


def _lire_surcharges_fenetre(
    company_id: str, periodes: list[tuple[int, int]]
) -> dict[tuple[int, int], date]:
    """Surcharges `company_variable_periods` des mois demandés et du mois d'avant."""
    from app.modules.payroll.application.periode_variables_service import _mois_precedent
    from postgrest.exceptions import APIError

    mois: set[tuple[int, int]] = set(periodes)
    for year, month in periodes:
        mois.add(_mois_precedent(year, month))
    annees = sorted({y for y, _ in mois})
    try:
        resp = (
            supabase.table("company_variable_periods")
            .select("year, month, end_date")
            .eq("company_id", str(company_id))
            .in_("year", annees)
            .execute()
        )
    except APIError as exc:
        if str(getattr(exc, "code", "") or "") == "PGRST205":
            return {}
        raise
    except Exception:  # noqa: BLE001 — table illisible : la règle société s'applique
        return {}
    retenues: dict[tuple[int, int], date] = {}
    for row in (resp.data if resp else None) or []:
        try:
            cle = (int(row["year"]), int(row["month"]))
        except (KeyError, TypeError, ValueError):
            continue
        if cle not in mois or not row.get("end_date"):
            continue
        try:
            retenues[cle] = date.fromisoformat(str(row["end_date"])[:10])
        except ValueError:
            continue
    return retenues


_EMPREINTES_DES_BULLETINS = (
    "year, month, "
    "empreinte_entrees:payslip_data->parametres->>empreinte_entrees, "
    "empreinte_cumuls_precedents:payslip_data->parametres->>empreinte_cumuls_precedents"
)


def lire_empreintes_des_bulletins(employee_id: str) -> list[dict[str, Any]]:
    """Mois, origine et empreintes de chaque bulletin du salarié — pas le bulletin.

    Sans la colonne `origine` (migration de reprise pas encore appliquée), tous
    les bulletins valent calculés, comme dans la liste.
    """
    from postgrest.exceptions import APIError

    for colonnes in (f"{_EMPREINTES_DES_BULLETINS}, origine", _EMPREINTES_DES_BULLETINS):
        try:
            resp = (
                supabase.table("payslips")
                .select(colonnes)
                .eq("employee_id", employee_id)
                .execute()
            )
        except APIError:
            if "origine" not in colonnes:
                raise
            continue
        return list((resp.data if resp else None) or [])
    return []


def lire_lectures_salarie(
    employee_id: str, periodes: list[tuple[int, int]]
) -> LecturesEmpreinte | None:
    """Tout ce qu'il faut pour l'empreinte des bulletins `periodes` de ce salarié."""
    if not employee_id or not periodes:
        return None
    fiche = (
        supabase.table("employees")
        .select(FICHE_COLONNES)
        .eq("id", employee_id)
        .maybe_single()
        .execute()
    )
    employee = (fiche.data if fiche else None) or None
    if not employee:
        return None
    from app.modules.payroll.documents.payslip_generator import resolve_date_sortie

    employee = {**employee, "exit_last_working_day": resolve_date_sortie(employee)}
    company_id = employee.get("company_id")
    company: dict[str, Any] = {}
    if company_id:
        societe = (
            supabase.table("companies")
            .select(SOCIETE_COLONNES)
            .eq("id", company_id)
            .maybe_single()
            .execute()
        )
        company = (societe.data if societe else None) or {}

    fenetre = _mois_a_lire(periodes)
    annees = sorted({y for y, _ in fenetre})
    mois = sorted({m for _, m in fenetre})
    plannings = (
        supabase.table("employee_schedules")
        # `cumuls` : ceux du mois d'avant, pour l'empreinte des cumuls précédents.
        .select("year, month, planned_calendar, actual_hours, cumuls")
        .eq("employee_id", employee_id)
        .in_("year", annees)
        .in_("month", mois)
        .execute()
    )
    calendriers: dict[tuple[int, int], dict[str, Any]] = {}
    for row in (plannings.data if plannings else None) or []:
        try:
            calendriers[(int(row["year"]), int(row["month"]))] = row
        except (KeyError, TypeError, ValueError):
            continue

    absences_res = (
        supabase.table("absence_requests")
        .select("type, selected_days")
        .eq("employee_id", employee_id)
        .eq("status", "validated")
        .execute()
    )
    absences = list((absences_res.data if absences_res else None) or [])

    periodes_demandees = set(periodes)
    annees_saisies = sorted({y for y, _ in periodes_demandees})
    mois_saisies = sorted({m for _, m in periodes_demandees})
    saisies_res = (
        supabase.table("monthly_inputs")
        .select(SAISIE_COLONNES)
        .eq("employee_id", employee_id)
        .in_("year", annees_saisies)
        .in_("month", mois_saisies)
        .execute()
    )
    saisies_par_mois: dict[tuple[int, int], list[dict[str, Any]]] = {}
    for row in (saisies_res.data if saisies_res else None) or []:
        try:
            cle = (int(row["year"]), int(row["month"]))
        except (KeyError, TypeError, ValueError):
            continue
        # `.in_(year).in_(month)` peut ramener un mois d'une autre année.
        if cle not in periodes_demandees:
            continue
        saisies_par_mois.setdefault(cle, []).append(row)

    notes: list[dict[str, Any]] = []
    plage = _plage_dates(fenetre)
    if plage:
        notes_res = (
            supabase.table("expense_reports")
            .select("type, amount, date")
            .eq("employee_id", employee_id)
            .eq("status", "validated")
            .gte("date", plage[0])
            .lte("date", plage[1])
            .execute()
        )
        notes = list((notes_res.data if notes_res else None) or [])

    surcharges_fenetre = _lire_surcharges_fenetre(company_id, periodes) if company_id else {}

    return LecturesEmpreinte(
        employee=employee,
        company=company,
        calendriers=calendriers,
        absences=absences,
        saisies_par_mois=saisies_par_mois,
        notes_de_frais=notes,
        surcharges_fenetre=surcharges_fenetre,
    )
