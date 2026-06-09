"""
Service applicatif du module dashboard.

Orchestration uniquement : utilise domain (règles pures), infrastructure
(repository, providers, mappers). Aucun accès DB ni FastAPI direct.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple

from app.core.database import get_supabase_client
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
from app.modules.employees.domain.deadline_reminders import (
    count_ending_trial_periods,
    count_expiring_cdds,
)
from app.modules.oeth_settings.infrastructure.boeth_repository import (
    boeth_profiles_repository,
)
from app.modules.dashboard.schemas.responses import (
    AbsentéismeDetail,
    ActionItems,
    AlertItems,
    AnalyticsAvances,
    DashboardData,
    KpiData,
    PayrollStatus,
    PyramideAge,
    ResidencePermitStats,
    TeamPulse,
    TurnoverStats,
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
        expiringContracts=count_expiring_cdds(all_employees, today),
        endOfTrialPeriods=count_ending_trial_periods(all_employees, today),
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

    handicapes_count = boeth_profiles_repository.count_active_by_company(company_id)

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
        handicapesCount=handicapes_count,
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


_TRANCHES_AGE_ORDER = ("< 25", "25-34", "35-44", "45-54", "55-64", "> 64")

_TYPES_MALADIE = frozenset(
    {
        "arret_maladie",
        "arret_maternite",
        "arret_paternite",
        "arret_maladie_pro",
    }
)
_TYPES_AT = frozenset(
    {
        "arret_at",
        "accident_travail",
        "accident_trajet",
    }
)


def _parse_date(value: Any) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None


def _salaire_brut_valeur(salaire: Any) -> float:
    if salaire is None:
        return 0.0
    if isinstance(salaire, dict) and "valeur" in salaire:
        try:
            return float(salaire["valeur"])
        except (TypeError, ValueError):
            return 0.0
    return 0.0


def _tranche_age(age: int) -> str:
    if age < 25:
        return "< 25"
    if age < 35:
        return "25-34"
    if age < 45:
        return "35-44"
    if age < 55:
        return "45-54"
    if age < 65:
        return "55-64"
    return "> 64"


def _classify_absence_type(abs_type: Any) -> str:
    t = (abs_type or "").strip().lower()
    if t in _TYPES_MALADIE:
        return "maladie"
    if t in _TYPES_AT:
        return "at"
    return "autres"


def _absence_weekdays_in_range(
    selected_days: Any, start: date, end: date, employee_ids: Set[str], emp_id: str
) -> int:
    if emp_id not in employee_ids:
        return 0
    total = 0
    for day_str in selected_days or []:
        try:
            d = date.fromisoformat(day_str) if isinstance(day_str, str) else day_str
            if isinstance(d, datetime):
                d = d.date()
            if start <= d <= end and d.weekday() < 5:
                total += 1
        except (ValueError, TypeError):
            continue
    return total


def _compute_absenteisme_window(
    absences: List[Dict[str, Any]],
    employee_ids: Set[str],
    start: date,
    end: date,
) -> Tuple[int, int, int, int, float]:
    """
    Retourne (jours_maladie, jours_at, jours_autres, jours_total, taux_global %).
    Dénominateur : effectif * jours ouvrés sur la fenêtre.
    """
    workdays = domain_rules.count_working_days_between(start, end)
    if workdays <= 0:
        workdays = 1
    n_emp = len(employee_ids)
    denom = float(workdays * n_emp) if n_emp else 1.0

    jm, ja, jo = 0, 0, 0
    for row in absences:
        if row.get("status") != "validated":
            continue
        eid = str(row.get("employee_id") or "")
        cat = _classify_absence_type(row.get("type"))
        n = _absence_weekdays_in_range(
            row.get("selected_days"), start, end, employee_ids, eid
        )
        if cat == "maladie":
            jm += n
        elif cat == "at":
            ja += n
        else:
            jo += n
    jtot = jm + ja + jo
    taux = round((jtot / denom) * 100.0, 2) if denom > 0 else 0.0
    return jm, ja, jo, jtot, taux


def build_analytics_avances(company_id: str) -> AnalyticsAvances:
    """
    Calcule les KPIs analytics avancés (turnover, pyramide d'âge, absentéisme,
    effectifs et masse salariale par service).
    """
    client = get_supabase_client()
    today = date.today()
    start_12m = today - timedelta(days=365)

    emp_resp = (
        client.table("employees")
        .select(
            "id, hire_date, date_naissance, employment_status, updated_at, "
            "service_id, salaire_de_base, contract_type"
        )
        .eq("company_id", company_id)
        .execute()
    )
    employees: List[Dict[str, Any]] = list(emp_resp.data or [])

    exits_resp = (
        client.table("employee_exits")
        .select("employee_id, last_working_day, updated_at")
        .eq("company_id", company_id)
        .execute()
    )
    exits_raw: List[Dict[str, Any]] = list(exits_resp.data or [])

    abs_resp = (
        client.table("absence_requests")
        .select("employee_id, type, selected_days, status")
        .eq("company_id", company_id)
        .execute()
    )
    absences_all: List[Dict[str, Any]] = list(abs_resp.data or [])

    services_resp = (
        client.table("company_services")
        .select("id, name")
        .eq("company_id", company_id)
        .execute()
    )
    service_names: Dict[str, str] = {}
    for srow in services_resp.data or []:
        if isinstance(srow, dict) and srow.get("id"):
            service_names[str(srow["id"])] = str(srow.get("name") or "Service")

    active_emps = [e for e in employees if (e.get("employment_status") or "") == "actif"]
    effectif_actif = len(active_emps)
    active_ids = {str(e["id"]) for e in active_emps if e.get("id")}

    # --- Turnover ---
    nb_embauches = 0
    for e in employees:
        hd = _parse_date(e.get("hire_date"))
        if hd and hd >= start_12m:
            nb_embauches += 1

    depart_ids: Set[str] = set()
    for ex in exits_raw:
        eid = str(ex.get("employee_id") or "")
        if not eid:
            continue
        lwd = _parse_date(ex.get("last_working_day"))
        if lwd is not None and start_12m <= lwd <= today:
            depart_ids.add(eid)
            continue
        if lwd is None:
            upd = _parse_date(ex.get("updated_at"))
            if upd and start_12m <= upd <= today:
                depart_ids.add(eid)

    for e in employees:
        if (e.get("employment_status") or "").lower() != "inactif":
            continue
        eid = str(e.get("id") or "")
        if not eid:
            continue
        upd = _parse_date(e.get("updated_at"))
        if upd and start_12m <= upd <= today:
            depart_ids.add(eid)

    nb_departs = len(depart_ids)
    denom_eff = float(effectif_actif) if effectif_actif > 0 else 1.0
    taux_turnover = round((nb_departs / denom_eff) * 100.0, 2)
    taux_embauches = round((nb_embauches / denom_eff) * 100.0, 2)
    taux_departs = taux_turnover

    turnover = TurnoverStats(
        taux_turnover_annuel=taux_turnover,
        nb_departs_12_mois=nb_departs,
        nb_embauches_12_mois=nb_embauches,
        taux_embauches=taux_embauches,
        taux_departs=taux_departs,
    )

    # --- Pyramide des âges (actifs avec date de naissance) ---
    counts_age: Dict[str, int] = {t: 0 for t in _TRANCHES_AGE_ORDER}
    for e in active_emps:
        bday = _parse_date(e.get("date_naissance"))
        if not bday:
            continue
        age = today.year - bday.year - (
            (today.month, today.day) < (bday.month, bday.day)
        )
        if age < 0:
            continue
        tr = _tranche_age(age)
        counts_age[tr] = counts_age.get(tr, 0) + 1

    total_pyramid = sum(counts_age.values())
    pyramide_ages: List[PyramideAge] = []
    for tr in _TRANCHES_AGE_ORDER:
        c = counts_age.get(tr, 0)
        pct = round((100.0 * c / total_pyramid), 2) if total_pyramid else 0.0
        pyramide_ages.append(PyramideAge(tranche=tr, count=c, pourcentage=pct))

    # --- Absentéisme 30j vs fenêtre précédente ---
    end_cur = today
    start_cur = today - timedelta(days=30)
    end_prev = start_cur - timedelta(days=1)
    start_prev = today - timedelta(days=60)

    jm_c, ja_c, jo_c, jtot_c, taux_c = _compute_absenteisme_window(
        absences_all, active_ids, start_cur, end_cur
    )
    jm_p, ja_p, jo_p, jtot_p, taux_p = _compute_absenteisme_window(
        absences_all, active_ids, start_prev, end_prev
    )

    if taux_p > 0:
        evolution = round(((taux_c - taux_p) / taux_p) * 100.0, 2)
    elif taux_c > 0 and taux_p == 0:
        evolution = 100.0
    else:
        evolution = 0.0

    wd_cur = domain_rules.count_working_days_between(start_cur, end_cur)
    wd_cur = wd_cur if wd_cur > 0 else 1
    denom_cur = float(wd_cur * effectif_actif) if effectif_actif else 1.0

    taux_maladie = round((jm_c / denom_cur) * 100.0, 2) if denom_cur else 0.0
    taux_at = round((ja_c / denom_cur) * 100.0, 2) if denom_cur else 0.0
    taux_autres = round((jo_c / denom_cur) * 100.0, 2) if denom_cur else 0.0

    absenteisme = AbsentéismeDetail(
        taux_global=taux_c,
        taux_maladie=taux_maladie,
        taux_at=taux_at,
        taux_autres=taux_autres,
        jours_perdus_total=jtot_c,
        jours_perdus_maladie=jm_c,
        jours_perdus_at=ja_c,
        jours_perdus_autres=jo_c,
        evolution_vs_mois_precedent=evolution,
    )

    # --- Effectif par service ---
    by_service: Dict[Optional[str], int] = defaultdict(int)
    salary_by_service: Dict[Optional[str], float] = defaultdict(float)
    by_contract: Dict[str, int] = defaultdict(int)

    for e in active_emps:
        sid = e.get("service_id")
        sk = str(sid) if sid else None
        by_service[sk] += 1
        salary_by_service[sk] += _salaire_brut_valeur(e.get("salaire_de_base"))
        ctype = e.get("contract_type") or "Non défini"
        by_contract[str(ctype)] += 1

    effectif_par_service: List[Dict] = []
    for sk, cnt in sorted(by_service.items(), key=lambda x: (-x[1], x[0] or "")):
        label = service_names.get(sk) if sk else "Sans service"
        if sk and label is None:
            label = "Service inconnu"
        effectif_par_service.append({"service": label, "count": cnt})

    effectif_par_contrat = [
        {"type": k, "count": v} for k, v in sorted(by_contract.items(), key=lambda x: -x[1])
    ]

    masse_rows: List[Dict[str, Any]] = []
    for sk, total_brut in salary_by_service.items():
        label = service_names.get(sk) if sk else "Sans service"
        if sk and label is None:
            label = "Service inconnu"
        masse_rows.append(
            {
                "service": label,
                "service_id": sk,
                "masse_salariale_brute": round(float(total_brut), 2),
            }
        )
    masse_rows.sort(key=lambda r: -float(r["masse_salariale_brute"]))
    masse_salariale_par_service: List[Dict] = masse_rows
    masse_salariale_brute_totale = round(
        sum(float(r["masse_salariale_brute"]) for r in masse_rows),
        2,
    )

    ages: List[int] = []
    tenures_years: List[float] = []
    for e in active_emps:
        bday = _parse_date(e.get("date_naissance"))
        if bday:
            age = today.year - bday.year - (
                (today.month, today.day) < (bday.month, bday.day)
            )
            if age >= 0:
                ages.append(age)
        hd = _parse_date(e.get("hire_date"))
        if hd and hd <= today:
            tenure_days = (today - hd).days
            if tenure_days >= 0:
                tenures_years.append(tenure_days / 365.25)

    age_moyen = round(sum(ages) / len(ages), 1) if ages else 0.0
    anciennete_moyenne_annees = (
        round(sum(tenures_years) / len(tenures_years), 1) if tenures_years else 0.0
    )

    return AnalyticsAvances(
        turnover=turnover,
        pyramide_ages=pyramide_ages,
        absenteisme=absenteisme,
        effectif_par_service=effectif_par_service,
        effectif_par_contrat=effectif_par_contrat,
        masse_salariale_par_service=masse_salariale_par_service,
        effectif_actif=effectif_actif,
        age_moyen=age_moyen,
        anciennete_moyenne_annees=anciennete_moyenne_annees,
        masse_salariale_brute_totale=masse_salariale_brute_totale,
    )
