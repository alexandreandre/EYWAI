"""Intégration modulation — calcul paie et compteurs salariés."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from app.core.database import supabase
from app.modules.modulation.application.hour_account_queries import (
    sync_account_balance_cache,
)
from app.modules.modulation.domain.entities import ModulationSettings
from app.modules.modulation.domain.hour_account_rules import (
    route_hs_for_period,
    sum_hs_from_payroll_events,
)
from app.modules.modulation.domain.rules import (
    compute_balance_hours,
    resolve_modulation_tier,
    theoretical_weekly_hours,
)
from app.modules.modulation.infrastructure import repository as repo


@dataclass(frozen=True)
class ModulationPayrollResult:
    hs_realisees: float = 0.0
    hs_credited: float = 0.0
    hs_paid: float = 0.0
    movement_ids: tuple[str, ...] = ()
    #: Heures de repos créditées (équivalent majoré des heures sup au compteur).
    repos_credite: float = 0.0
    #: La RH a choisi, pour ce mois, de tout payer au lieu de mettre au compteur.
    paye_ce_mois: bool = False
    #: La RH a choisi, pour ce mois, de mettre au compteur (société qui paie).
    au_compteur_ce_mois: bool = False
    #: La règle de la société : l'écran du bulletin offre le choix du mois pour
    #: « tout au compteur » et « tout payer ».
    regle: str = ""
    #: Heures saisies à la main qui restent à payer (25 %, 50 %) ; None sans saisie.
    declaration_restante: tuple[float, float] | None = None


def _monday_of_week(d: date) -> date:
    return d - timedelta(days=d.weekday())


def build_modulation_weekly_hours_map(
    settings: ModulationSettings,
    year: int,
) -> dict[tuple[int, int], float]:
    """Carte (année ISO, semaine ISO) → heures théoriques modulation."""
    if not settings.enabled:
        return {}
    out: dict[tuple[int, int], float] = {}
    d = date(year, 1, 1)
    end = date(year, 12, 31)
    while d <= end:
        monday = _monday_of_week(d)
        iso = monday.isocalendar()
        key = (iso[0], iso[1])
        if key not in out:
            tier = resolve_modulation_tier(monday, settings)
            out[key] = theoretical_weekly_hours(tier, settings)
        d += timedelta(days=7)
    return out


def _sum_hours_from_actual(actual: dict[str, Any] | None) -> float:
    if not actual or not isinstance(actual, dict):
        return 0.0
    total = 0.0
    for day_data in actual.values():
        if isinstance(day_data, dict):
            total += float(day_data.get("heures_faites") or 0)
        elif isinstance(day_data, (int, float)):
            total += float(day_data)
    return round(total, 2)


def _theoretical_hours_for_year(settings: ModulationSettings, year: int) -> float:
    weekly_map = build_modulation_weekly_hours_map(settings, year)
    return round(sum(weekly_map.values()), 2)


def sync_employee_modulation_counter(
    company_id: str,
    employee_id: str,
    year: int,
    *,
    settings: ModulationSettings | None = None,
    period_credited_hours: float | None = None,
    period_paid_hours: float | None = None,
) -> None:
    """Met à jour le compteur annuel théorique / réalisé / solde + cache compte."""
    settings = settings or repo.get_modulation_settings(company_id)
    if not settings.enabled and not settings.hour_account_enabled:
        return

    actual_total = 0.0
    theoretical = 0.0
    balance = 0.0
    if settings.enabled:
        resp = (
            supabase.table("employee_schedules")
            .select("month, actual_hours")
            .eq("employee_id", employee_id)
            .eq("year", year)
            .execute()
        )
        for row in resp.data or []:
            actual_total += _sum_hours_from_actual(row.get("actual_hours"))
        theoretical = _theoretical_hours_for_year(settings, year)
        balance = compute_balance_hours(theoretical, actual_total)

    account_balance = 0.0
    if settings.hour_account_enabled:
        account_balance = sync_account_balance_cache(company_id, employee_id, year)

    repo.upsert_employee_counter(
        company_id,
        employee_id,
        year,
        theoretical,
        actual_total,
        balance,
        account_balance_hours=account_balance,
        period_credited_hours=period_credited_hours,
        period_paid_hours=period_paid_hours,
    )


def _decision_du_mois(employee_id: str, year: int, month: int) -> dict[str, Any] | None:
    """La décision de la RH pour ce salarié et ce mois (« payer ces heures »).

    Validée ou déjà appliquée par une génération : un recalcul en bac à sable
    (qui ne rouvre rien) doit la lire comme la génération réelle."""
    from app.modules.modulation.infrastructure import overtime_routing_repository as otr_repo

    decision = otr_repo.get_decision(employee_id, year, month)
    if decision and str(decision.get("status")) in ("validated", "applied_payroll"):
        return decision
    return None


def apply_modulation_hour_account_to_calendar(
    company_id: str,
    employee_id: str,
    year: int,
    month: int,
    calendrier_etendu: list[dict[str, Any]],
    *,
    persister: bool = True,
    bornes_variables: tuple[date, date] | None = None,
    majorations: dict[str, float] | None = None,
    heures_declarees: tuple[float, float] | None = None,
) -> tuple[list[dict[str, Any]], list[str], ModulationPayrollResult]:
    """Met au compteur de récupération les heures sup du mois que la paie ne
    paie pas, à l'équivalent majoré (spec 2026-11-05-heures-de-recuperation).

    - `bornes_variables` : la fenêtre où la paie compte les heures sup ;
    - `majorations` : les taux du barème de la société (25 % / 50 % à défaut) ;
    - `heures_declarees` : heures sup saisies à la main (25 %, 50 %), qui font foi
      sur le planning ; ce qu'il en reste à payer revient dans le résultat.
    `persister=False` (bac à sable) : même calcul, aucun mouvement écrit.
    """
    settings = repo.get_modulation_settings(company_id)
    if not settings.hour_account_enabled:
        return calendrier_etendu, [], ModulationPayrollResult()
    calendrier_d_origine = calendrier_etendu

    from app.modules.modulation.domain.hour_account_rules import (
        mettre_hs_au_compteur,
        mouvements_hors_paie_du_mois,
        remplacer_hs_par_declaration,
        solde_au,
    )

    if heures_declarees is not None:
        calendrier_etendu = remplacer_hs_par_declaration(
            calendrier_etendu, heures_declarees[0], heures_declarees[1], bornes_variables
        )

    # Le crédit qu'une génération précédente du mois a posé est refait ici :
    # il ne compte ni dans le solde ni dans la franchise (recalcul, bac à sable).
    mouvements = mouvements_hors_paie_du_mois(
        repo.list_movements_for_employee(employee_id), year, month
    )
    solde = solde_au(mouvements, year, month)

    sonde = mettre_hs_au_compteur(
        calendrier_etendu, majorations=majorations, bornes=bornes_variables
    )
    total_hs = round(sonde.heures_sup_au_compteur, 2)
    if total_hs <= 0:
        if settings.hs_routing_policy == "pay_all":
            return (
                calendrier_d_origine,
                [],
                ModulationPayrollResult(hs_realisees=0.0, regle="pay_all"),
            )
        return (
            calendrier_etendu,
            [],
            ModulationPayrollResult(
                hs_realisees=0.0,
                regle=settings.hs_routing_policy,
                declaration_restante=(0.0, 0.0) if heures_declarees is not None else None,
            ),
        )

    policy = settings.hs_routing_policy
    decision = _decision_du_mois(employee_id, year, month)
    plafond = settings.max_account_balance_hours
    if policy == "pay_all" and (
        decision is None or float(decision.get("hours_to_account") or 0) <= 0
    ):
        # La société paie ses heures sup : calendrier et saisies ne bougent pas.
        # Le total sert à l'écran (« Mettre ces heures au compteur »).
        return (
            calendrier_d_origine,
            [],
            ModulationPayrollResult(hs_realisees=total_hs, hs_paid=total_hs, regle=policy),
        )
    if decision is not None:
        # Choix du mois par la RH (« payer ces heures ce mois-ci »), quelle que
        # soit la règle de la société.
        a_payer = max(0.0, total_hs - float(decision.get("hours_to_account") or 0))
    elif policy == "manual":
        # Sans décision, rien ne part au compteur.
        a_payer = total_hs
    elif policy == "franchise":
        split = route_hs_for_period(
            total_hs,
            "franchise",
            float(settings.hs_franchise_hours_per_period or 0),
            0.0,
            solde,
            None,
        )
        a_payer = split.to_pay
    else:  # account_all
        a_payer = 0.0

    mise = mettre_hs_au_compteur(
        calendrier_etendu,
        majorations=majorations,
        bornes=bornes_variables,
        solde=solde,
        plafond=plafond,
        heures_a_payer=a_payer,
    )

    movement_ids: list[str] = []
    if mise.repos_credite > 0 and persister:
        row = repo.insert_movement(
            {
                "company_id": company_id,
                "employee_id": employee_id,
                "year": year,
                "month": month,
                "movement_type": "credit_hs",
                "hours": mise.repos_credite,
                "status": "validated",
                "source": "payroll_auto",
                "metadata": {
                    "hs_realisees": total_hs,
                    "hs_au_compteur": mise.heures_sup_au_compteur,
                    "hs_paid": mise.heures_sup_payees,
                    "heures_par_type": mise.heures_par_type,
                },
            }
        )
        movement_ids.append(str(row["id"]))
        sync_account_balance_cache(company_id, employee_id, year)

    if persister:
        sync_employee_modulation_counter(
            company_id,
            employee_id,
            year,
            settings=settings,
            period_credited_hours=mise.repos_credite,
            period_paid_hours=mise.heures_sup_payees,
        )

    calendrier_final = mise.calendrier
    restante: tuple[float, float] | None = None
    if heures_declarees is not None:
        # Ce qui reste des heures saisies retourne au moteur par la saisie :
        # elles sortent du calendrier, qui ne doit pas les compter en plus.
        def _reste(type_hs: str) -> float:
            return round(
                sum(
                    float(e.get("heures") or 0)
                    for e in calendrier_final
                    if e.get("declaree") and e.get("type") == type_hs
                ),
                2,
            )

        restante = (_reste("travail_hs25"), _reste("travail_hs50"))
        calendrier_final = [e for e in calendrier_final if not e.get("declaree")]

    return (
        calendrier_final,
        movement_ids,
        ModulationPayrollResult(
            hs_realisees=total_hs,
            hs_credited=mise.heures_sup_au_compteur,
            hs_paid=mise.heures_sup_payees,
            movement_ids=tuple(movement_ids),
            repos_credite=mise.repos_credite,
            paye_ce_mois=(
                decision is not None and float(decision.get("hours_to_account") or 0) <= 0
            ),
            au_compteur_ce_mois=(
                decision is not None and float(decision.get("hours_to_account") or 0) > 0
            ),
            regle=policy,
            declaration_restante=restante,
        ),
    )


def etat_recuperation_du_bulletin(
    company_id: str,
    employee_id: str,
    year: int,
    month: int,
    *,
    credit_du_calcul: float | None = None,
) -> dict[str, Any] | None:
    """Le compteur de récupération que le bulletin du mois imprime ; None quand
    la société n'a pas de compteur (rien ne change sur son bulletin).

    `credit_du_calcul` : le crédit du calcul en cours, qui remplace celui d'une
    génération précédente ; None pour lire le compteur tel qu'il est en base."""
    settings = repo.get_modulation_settings(company_id)
    if not settings.hour_account_enabled:
        return None
    from app.modules.modulation.domain.hour_account_rules import etat_du_mois, solde_payable

    mouvements = repo.list_movements_for_employee(employee_id)
    if settings.hs_routing_policy == "pay_all" and not mouvements and not credit_du_calcul:
        # Société qui paie ses heures sup, salarié sans compteur : rien à imprimer.
        # S'il a un solde (reprise de Quadra, société repassée en « payées »), il
        # reste dû et visible.
        return None
    return {
        **etat_du_mois(
            mouvements,
            year,
            month,
            credit_du_calcul=None if credit_du_calcul is None else float(credit_du_calcul),
        ),
        "payable": solde_payable(mouvements, year, month),
    }


def apply_modulation_to_payroll_events(
    payroll_events: list[dict[str, Any]],
    hours_to_defer: float,
) -> tuple[list[dict[str, Any]], float]:
    """Réduit les HS dans les événements de paie (analyse calendrier)."""
    from app.modules.modulation.domain.hour_account_rules import reduce_payroll_hs_events

    return reduce_payroll_hs_events(payroll_events, hours_to_defer)


def enrich_payroll_events_metadata(
    payroll_events_json: dict[str, Any],
    events_list: list[dict[str, Any]],
    modulation_result: ModulationPayrollResult | None = None,
) -> dict[str, Any]:
    """Ajoute hs_realisees_mois et champs compte modulation aux payroll_events."""
    out = dict(payroll_events_json)
    out["hs_realisees_mois"] = sum_hs_from_payroll_events(events_list)
    if modulation_result:
        out["modulation_account_credited_hours"] = modulation_result.hs_credited
        out["modulation_account_paid_hs_hours"] = modulation_result.hs_paid
    return out


def finalize_modulation_payroll_application(
    movement_ids: list[str],
    *,
    employee_id: str | None = None,
    year: int | None = None,
    month: int | None = None,
) -> None:
    repo.mark_movements_applied_payroll(movement_ids)
    if employee_id and year and month:
        from app.modules.modulation.infrastructure import overtime_routing_repository as otr_repo

        otr_repo.mark_applied_payroll(employee_id, year, month)


def defaire_credits_de_paie(employee_id: str, year: int, month: int) -> int:
    """Avant de recalculer le bulletin du mois, ou en le supprimant : retire les
    heures sup qu'il a créditées au compte et rouvre la décision de routage.

    Sans cela, le recalcul comptait ce crédit dans la franchise déjà consommée
    et dans le solde : les heures étaient créditées et payées, ou créditées deux
    fois ; et une décision « appliquée » n'étant plus « validée », toutes les
    heures sup étaient payées.
    """
    from app.modules.modulation.infrastructure import overtime_routing_repository as otr_repo

    retires = repo.supprimer_credits_de_paie(employee_id, year, month)
    otr_repo.rouvrir_decision(employee_id, year, month)
    if retires:
        sync_employee_modulation_counter(str(retires[0]["company_id"]), employee_id, year)
    return len(retires)


def compute_pay_smoothing_gain(
    company_id: str,
    year: int,
    month: int,
    hourly_rate: float,
) -> float:
    from app.modules.modulation.domain.pay_smoothing_rules import (
        compute_smoothing_gain_for_month,
    )

    settings = repo.get_modulation_settings(company_id)
    return compute_smoothing_gain_for_month(settings, year, month, hourly_rate)


def week_config_from_template(day_configs: list[dict[str, Any]] | None) -> dict[str, Any]:
    """Convertit day_configs DB en WeekConfig apply-model."""
    day_keys = [
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
        "sunday",
    ]
    default_work = {"type": "travail", "hours": 8.0}
    default_weekend = {"type": "weekend", "hours": 0.0}
    week: dict[str, Any] = {k: dict(default_weekend) for k in day_keys}
    for i, k in enumerate(day_keys[:5]):
        week[k] = dict(default_work)
    for cfg in day_configs or []:
        day_num = int(cfg.get("day") or 0)
        if 1 <= day_num <= 7:
            key = day_keys[day_num - 1]
            hours = float(cfg.get("hours") or 0)
            day_type = str(cfg.get("type") or "travail")
            if day_type == "repos" or hours <= 0:
                week[key] = {"type": "weekend", "hours": 0.0}
            else:
                week[key] = {"type": "travail", "hours": hours}
    return week
