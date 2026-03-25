"""
Service applicatif du module dashboard.

Orchestration uniquement : utilise domain (règles pures), infrastructure
(repository, providers, mappers). Aucun accès DB ni FastAPI direct.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta

from app.modules.dashboard.application.dto import MONTH_NAMES_FR
from app.modules.dashboard.domain import rules as domain_rules
from app.modules.dashboard.infrastructure.mappers import (
    aggregate_payslip_costs_and_net,
    to_chart_data_points,
    to_simple_employees,
    to_team_pulse_employees,
    to_team_pulse_events,
)
from app.modules.dashboard.infrastructure.providers import (
    get_residence_permit_calculator,
)
from app.modules.dashboard.infrastructure.repository import get_dashboard_repository
from app.modules.dashboard.schemas.responses import (
    ActionItems,
    AlertItems,
    DashboardData,
    KpiData,
    PayrollStatus,
    ResidencePermitStats,
    TeamPulse,
)


def get_residence_permit_stats(company_id: str) -> ResidencePermitStats:
    """
    Statistiques agrégées des titres de séjour pour le dashboard.
    Utilise le provider (ResidencePermitService) pour cohérence fiche employé.
    """
    try:
        repo = get_dashboard_repository()
        employees = repo.get_employees_for_residence_permit_stats(company_id)
        calculator = get_residence_permit_calculator()
        today = date.today()

        total_expire = 0
        total_a_renouveler = 0
        total_a_renseigner = 0
        total_valide = 0

        for emp in employees:
            is_subject = emp.get("is_subject_to_residence_permit", False)
            expiry_date_str = emp.get("residence_permit_expiry_date")
            employment_status = emp.get("employment_status", "actif")

            expiry_date = None
            if expiry_date_str:
                if isinstance(expiry_date_str, str):
                    expiry_date = date.fromisoformat(expiry_date_str)
                elif isinstance(expiry_date_str, date):
                    expiry_date = expiry_date_str

            status_data = calculator.calculate_residence_permit_status(
                is_subject_to_residence_permit=is_subject,
                residence_permit_expiry_date=expiry_date,
                employment_status=employment_status,
                reference_date=today,
            )
            status = status_data.get("residence_permit_status")

            if status == "expired":
                total_expire += 1
            elif status == "to_renew":
                total_a_renouveler += 1
            elif status == "to_complete":
                total_a_renseigner += 1
            elif status == "valid":
                total_valide += 1

        return ResidencePermitStats(
            total_expire=total_expire,
            total_a_renouveler=total_a_renouveler,
            total_a_renseigner=total_a_renseigner,
            total_valide=total_valide,
        )
    except Exception as e:
        logging.error(
            "Erreur lors du calcul des statistiques de titres de séjour: %s",
            e,
            exc_info=True,
        )
        return ResidencePermitStats(
            total_expire=0,
            total_a_renouveler=0,
            total_a_renseigner=0,
            total_valide=0,
        )


def build_full_dashboard(company_id: str) -> DashboardData:
    """
    Agrège toutes les données du cockpit RH pour une entreprise.
    Comportement identique à l'ancien endpoint GET /api/dashboard/all.
    """
    repo = get_dashboard_repository()
    today = date.today()

    all_employees = repo.get_employees_for_dashboard(company_id)
    absences_count = repo.get_pending_absence_requests_count(company_id)
    expenses_count = repo.get_pending_expense_reports_count(company_id)

    alerts = AlertItems(
        obsoleteRates=0,
        expiringContracts=0,
        endOfTrialPeriods=0,
    )

    # Team pulse : absents du jour + événements à venir
    absences_today_raw = repo.get_absence_requests_validated_today(company_id)
    absent_today = to_team_pulse_employees(absences_today_raw)
    events_raw = domain_rules.build_upcoming_events_raw(
        all_employees, today, window_days=7
    )
    upcoming_events = to_team_pulse_events(events_raw)

    # Paie : agrégation par mois
    payslips = repo.get_payslips_by_company(company_id)
    costs_by_month, net_by_month = aggregate_payslip_costs_and_net(payslips)

    current_month = today.month
    all_months = set(costs_by_month.keys()) | set(net_by_month.keys())
    sorted_months = domain_rules.get_last_n_past_months(all_months, current_month, n=12)
    chart_data = to_chart_data_points(
        costs_by_month,
        net_by_month,
        sorted_months,
        month_names=MONTH_NAMES_FR,
    )

    # KPIs : mois précédent
    prev_month_num, prev_year = domain_rules.get_previous_month(today)
    current_month_str = f"{prev_month_num:02d}/{prev_year}"
    cout_total_mois_actuel = costs_by_month.get(prev_month_num, 0)
    net_verse_mois_actuel = net_by_month.get(prev_month_num, 0)

    # Taux d'absentéisme (règles pures + données infra)
    employee_ids = [e["id"] for e in all_employees]
    thirty_days_ago = today - timedelta(days=30)
    working_days = domain_rules.count_working_days_between(thirty_days_ago, today)
    theoretical_working_days = working_days * len(employee_ids) if employee_ids else 0

    if theoretical_working_days > 0:
        absences_for_rate = repo.get_absence_requests_for_absenteeism(company_id)
        total_absence_days = domain_rules.count_absence_days_in_range(
            absences_for_rate,
            set(employee_ids),
            thirty_days_ago,
            today,
        )
        taux_absenteisme_reel = domain_rules.compute_absenteeism_rate(
            total_absence_days,
            theoretical_working_days,
        )
    else:
        taux_absenteisme_reel = 0.0

    contract_distribution = domain_rules.aggregate_contract_distribution(all_employees)
    cdi_count = sum(1 for e in all_employees if e.get("contract_type") == "CDI")
    cdd_count = sum(1 for e in all_employees if e.get("contract_type") == "CDD")

    kpis = KpiData(
        coutTotal=round(cout_total_mois_actuel, 2),
        netVerse=round(net_verse_mois_actuel, 2),
        effectifActif=len(all_employees),
        tauxAbsenteisme=taux_absenteisme_reel,
        currentMonth=current_month_str,
        cdiCount=cdi_count,
        cddCount=cdd_count,
        contractDistribution=contract_distribution,
        hommesCount=None,
        femmesCount=None,
        handicapesCount=None,
    )

    simple_employees_list = to_simple_employees(all_employees)
    payroll_status = PayrollStatus(
        currentMonth=today.strftime("%B %Y"),
        step=1,
        totalSteps=4,
    )

    return DashboardData(
        kpis=kpis,
        chartData=chart_data,
        actions=ActionItems(
            pendingAbsences=absences_count,
            pendingExpenses=expenses_count,
        ),
        alerts=alerts,
        teamPulse=TeamPulse(
            absentToday=absent_today,
            upcomingEvents=upcoming_events,
        ),
        employees=simple_employees_list,
        payrollStatus=payroll_status,
    )
