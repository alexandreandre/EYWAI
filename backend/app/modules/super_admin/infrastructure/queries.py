"""
Requêtes DB du module super_admin (infrastructure).

Lecture Supabase : dashboard, companies, users, health, réduction Fillon.
Comportement identique à l'application ; pas de FastAPI.
"""

from __future__ import annotations

import calendar
import json
from typing import Any, Dict, List, Optional

from app.core.database import get_supabase_admin_client, get_supabase_client
from app.modules.audit.infrastructure.repository import audit_repository
from app.modules.scraping.infrastructure.repository import ScrapingRepository

_scraping_repo = ScrapingRepository()


def _support_ticket_stats(supabase: Any) -> Dict[str, Any]:
    """Compteurs tickets support pour le dashboard admin."""
    try:
        result = supabase.table("support_tickets").select("status, urgency").execute()
        rows = result.data or []
    except Exception:
        return {"open": 0, "urgent": 0, "by_status": {}}
    by_status: Dict[str, int] = {}
    open_count = 0
    urgent = 0
    open_statuses = {"envoye", "en_cours"}
    for row in rows:
        st = row.get("status") or "unknown"
        by_status[st] = by_status.get(st, 0) + 1
        if st in open_statuses:
            open_count += 1
            if row.get("urgency") in ("critique", "elevee"):
                urgent += 1
    return {"open": open_count, "urgent": urgent, "by_status": by_status}


def _recent_support_tickets(supabase: Any, limit: int = 5) -> List[Dict[str, Any]]:
    try:
        r = (
            supabase.table("support_tickets")
            .select("id, company_id, module, urgency, status, description, created_at, companies(company_name)")
            .in_("status", ["envoye", "en_cours"])
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        out: List[Dict[str, Any]] = []
        for row in r.data or []:
            companies = row.pop("companies", None)
            name = None
            if isinstance(companies, dict):
                name = companies.get("company_name")
            elif isinstance(companies, list) and companies:
                name = companies[0].get("company_name")
            out.append({**row, "company_name": name})
        return out
    except Exception:
        return []


def get_support_badges() -> Dict[str, int]:
    """Badges sidebar : tickets en attente et urgents."""
    supabase = get_supabase_client()
    stats = _support_ticket_stats(supabase)
    return {"pending": stats["open"], "urgent": stats["urgent"]}


def list_platform_audit_logs(
    company_id: Optional[str] = None,
    user_id: Optional[str] = None,
    action: Optional[str] = None,
    resource_type: Optional[str] = None,
    created_after: Optional[str] = None,
    created_before: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    return audit_repository.list_logs_platform(
        company_id=company_id,
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        created_after=created_after,
        created_before=created_before,
        limit=limit,
        offset=offset,
    )


def get_global_stats(_super_admin_row: Dict[str, Any]) -> Dict[str, Any]:
    """Statistiques globales pour GET /dashboard/stats."""
    supabase = get_supabase_client()
    companies = (
        supabase.table("companies").select("id, is_active", count="exact").execute()
    )
    companies_active = [c for c in companies.data if c.get("is_active", False)]
    profiles = (
        supabase.table("profiles")
        .select("id, role, company_id", count="exact")
        .execute()
    )
    employees = (
        supabase.table("employees").select("id, company_id", count="exact").execute()
    )
    super_admins = (
        supabase.table("super_admins")
        .select("id", count="exact")
        .eq("is_active", True)
        .execute()
    )
    roles_count: Dict[str, int] = {}
    for profile in profiles.data:
        role = profile.get("role", "unknown")
        roles_count[role] = roles_count.get(role, 0) + 1
    company_employee_count: Dict[str, int] = {}
    for emp in employees.data:
        comp_id = emp.get("company_id")
        if comp_id:
            company_employee_count[comp_id] = company_employee_count.get(comp_id, 0) + 1
    top_companies = sorted(
        company_employee_count.items(), key=lambda x: x[1], reverse=True
    )[:5]
    top_companies_with_names: List[Dict[str, Any]] = []
    for comp_id, emp_count in top_companies:
        comp_data = (
            supabase.table("companies")
            .select("company_name")
            .eq("id", comp_id)
            .execute()
        )
        if comp_data.data:
            top_companies_with_names.append(
                {
                    "id": comp_id,
                    "name": comp_data.data[0]["company_name"],
                    "employees_count": emp_count,
                }
            )
    support_stats = _support_ticket_stats(supabase)
    unread_alerts = _scraping_repo.get_unread_alerts(limit=100)
    recent_activity = audit_repository.list_logs_platform(limit=10, offset=0)
    recent_tickets = _recent_support_tickets(supabase, limit=5)

    return {
        "companies": {
            "total": companies.count,
            "active": len(companies_active),
            "inactive": companies.count - len(companies_active),
        },
        "users": {"total": profiles.count, "by_role": roles_count},
        "employees": {"total": employees.count},
        "platform_admins": {"total": super_admins.count},
        "super_admins": {"total": super_admins.count},
        "top_companies": top_companies_with_names,
        "support_tickets": support_stats,
        "scraping_alerts": {"unread": len(unread_alerts)},
        "recent_activity": recent_activity,
        "recent_support_tickets": recent_tickets,
    }


def list_companies(
    skip: int = 0,
    limit: int = 50,
    search: Optional[str] = None,
    is_active: Optional[bool] = None,
) -> Dict[str, Any]:
    """Liste des entreprises avec filtres. Retourne { companies, total }."""
    supabase = get_supabase_client()
    query = supabase.table("companies").select("*, company_groups(group_name)")
    if is_active is not None:
        query = query.eq("is_active", is_active)
    if search:
        query = query.or_(
            f"company_name.ilike.%{search}%,siret.ilike.%{search}%,email.ilike.%{search}%"
        )
    query = query.range(skip, skip + limit - 1).order("created_at", desc=True)
    result = query.execute()
    for company in result.data:
        company_id = company["id"]
        if "company_groups" in company and company["company_groups"]:
            company["group_name"] = company["company_groups"].get("group_name")
            del company["company_groups"]
        else:
            company["group_name"] = None
        emp_count = (
            supabase.table("employees")
            .select("id", count="exact")
            .eq("company_id", company_id)
            .execute()
        )
        company["employees_count"] = emp_count.count
        users_count = (
            supabase.table("user_company_accesses")
            .select("user_id", count="exact")
            .eq("company_id", company_id)
            .execute()
        )
        company["users_count"] = users_count.count
    return {"companies": result.data, "total": len(result.data)}


def get_company_details(company_id: str) -> Dict[str, Any]:
    """Détails d'une entreprise + stats (employees_count, users_count, users_by_role)."""
    supabase = get_supabase_client()
    company = supabase.table("companies").select("*").eq("id", company_id).execute()
    if not company.data:
        raise LookupError("Entreprise non trouvée")
    company_data = company.data[0]
    employees = (
        supabase.table("employees").select("id").eq("company_id", company_id).execute()
    )
    user_accesses = (
        supabase.table("user_company_accesses")
        .select("user_id, role")
        .eq("company_id", company_id)
        .execute()
    )
    roles_count: Dict[str, int] = {}
    for access in user_accesses.data:
        role = access.get("role", "unknown")
        roles_count[role] = roles_count.get(role, 0) + 1
    company_data["stats"] = {
        "employees_count": len(employees.data),
        "users_count": len(user_accesses.data),
        "users_by_role": roles_count,
    }
    try:
        jei_res = (
            supabase.table("company_jei_settings")
            .select("jei_enabled, date_creation_etablissement, taux_exoneration")
            .eq("company_id", company_id)
            .maybe_single()
            .execute()
        )
        jei_row = jei_res.data if jei_res else None
        if jei_row:
            company_data["jei_enabled"] = bool(jei_row.get("jei_enabled"))
            company_data["date_creation_etablissement"] = jei_row.get(
                "date_creation_etablissement"
            )
            company_data["taux_exoneration"] = jei_row.get("taux_exoneration")
        else:
            company_data["jei_enabled"] = False
            company_data["date_creation_etablissement"] = None
            company_data["taux_exoneration"] = 1.0
    except Exception:
        company_data["jei_enabled"] = False
        company_data["date_creation_etablissement"] = None
        company_data["taux_exoneration"] = 1.0
    return company_data


def list_all_users(
    skip: int = 0,
    limit: int = 50,
    company_id: Optional[str] = None,
    role: Optional[str] = None,
    search: Optional[str] = None,
) -> Dict[str, Any]:
    """Liste tous les utilisateurs (avec emails via admin client). Retourne { users, total }."""
    supabase = get_supabase_client()
    admin_client = get_supabase_admin_client()
    query = supabase.table("profiles").select("*")
    if company_id:
        query = query.eq("company_id", company_id)
    if role:
        query = query.eq("role", role)
    if search:
        query = query.or_(f"first_name.ilike.%{search}%,last_name.ilike.%{search}%")
    query = query.range(skip, skip + limit - 1).order("created_at", desc=True)
    result = query.execute()
    for user in result.data:
        if user.get("company_id"):
            comp = (
                supabase.table("companies")
                .select("company_name")
                .eq("id", user["company_id"])
                .execute()
            )
            user["company_name"] = (
                comp.data[0]["company_name"] if comp.data else "Inconnue"
            )
        try:
            auth_response = admin_client.auth.admin.get_user_by_id(user["id"])
            user["email"] = (
                auth_response.user.email
                if auth_response and auth_response.user
                else None
            )
        except Exception:
            user["email"] = None
    return {"users": result.data, "total": len(result.data)}


def get_company_users(
    company_id: str,
    role: Optional[str] = None,
) -> Dict[str, Any]:
    """Utilisateurs ayant accès à une entreprise (user_company_accesses + profiles + emails)."""
    supabase = get_supabase_client()
    admin_client = get_supabase_admin_client()
    company = supabase.table("companies").select("id").eq("id", company_id).execute()
    if not company.data:
        raise LookupError("Entreprise non trouvée")
    accesses_query = (
        supabase.table("user_company_accesses")
        .select("user_id, role")
        .eq("company_id", company_id)
    )
    if role:
        accesses_query = accesses_query.eq("role", role)
    accesses_result = accesses_query.execute()
    user_ids_from_accesses = {
        acc["user_id"]: acc["role"] for acc in accesses_result.data
    }
    if user_ids_from_accesses:
        profiles_result = (
            supabase.table("profiles")
            .select("*")
            .in_("id", list(user_ids_from_accesses.keys()))
            .order("created_at", desc=True)
            .execute()
        )
        result_data = profiles_result.data
    else:
        result_data = []
    users_with_email: List[Dict[str, Any]] = []
    for user in result_data:
        try:
            auth_response = admin_client.auth.admin.get_user_by_id(user["id"])
            user["email"] = (
                auth_response.user.email
                if auth_response and auth_response.user
                else None
            )
        except Exception:
            user["email"] = None
        user["role"] = user_ids_from_accesses.get(
            user["id"], user.get("role", "collaborateur")
        )
        users_with_email.append(user)
    return {"users": users_with_email, "total": len(users_with_email)}


def list_super_admins() -> Dict[str, Any]:
    """Liste tous les super admins. Retourne { super_admins, total }."""
    supabase = get_supabase_client()
    result = (
        supabase.table("super_admins")
        .select("*")
        .order("created_at", desc=True)
        .execute()
    )
    return {
        "platform_admins": result.data,
        "super_admins": result.data,
        "total": len(result.data),
    }


def get_system_health() -> Dict[str, Any]:
    """État de santé (RPC check_company_data_integrity)."""
    supabase = get_supabase_client()
    try:
        integrity_check = supabase.rpc("check_company_data_integrity").execute()
        has_issues = len(integrity_check.data) > 0 if integrity_check.data else False
        return {
            "status": "degraded" if has_issues else "healthy",
            "checks": {
                "database": "ok",
                "data_integrity": "issues_found" if has_issues else "ok",
            },
            "integrity_issues": integrity_check.data if has_issues else [],
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


def get_employees_for_reduction_fillon() -> Dict[str, Any]:
    """Liste des employés pour le test réduction Fillon."""
    supabase = get_supabase_client()
    employees_res = (
        supabase.table("employees")
        .select(
            "id, first_name, last_name, company_id, salaire_de_base, duree_hebdomadaire, statut, job_title"
        )
        .execute()
    )
    employees = employees_res.data or []
    company_ids = list(
        set(e.get("company_id") for e in employees if e.get("company_id"))
    )
    companies_res = (
        supabase.table("companies")
        .select("id, company_name")
        .in_("id", company_ids)
        .execute()
        if company_ids
        else None
    )
    companies_map = (
        {c["id"]: c["company_name"] for c in (companies_res.data or [])}
        if companies_res
        else {}
    )
    available_employees: List[Dict[str, Any]] = []
    for emp in employees:
        salaire = emp.get("salaire_de_base", {})
        if isinstance(salaire, str):
            salaire = json.loads(salaire)
        salaire_valeur = salaire.get("valeur", 0) if isinstance(salaire, dict) else 0
        available_employees.append(
            {
                "id": emp["id"],
                "name": f"{emp.get('first_name', '')} {emp.get('last_name', '')}".strip(),
                "company_name": companies_map.get(emp.get("company_id"), ""),
                "salaire_base": salaire_valeur,
                "duree_hebdomadaire": emp.get("duree_hebdomadaire", 35),
                "statut": emp.get("statut", "Non-Cadre"),
                "job_title": emp.get("job_title", ""),
            }
        )
    return {"employees": available_employees, "total": len(available_employees)}


def calculate_reduction_fillon(
    employee_id: str, month: int, year: int
) -> Dict[str, Any]:
    """Calcule la réduction Fillon pour un employé/mois. Structure détaillée identique au legacy."""
    supabase = get_supabase_client()
    employee_res = (
        supabase.table("employees").select("*").eq("id", employee_id).single().execute()
    )
    if not employee_res.data:
        raise LookupError("Employé non trouvé")
    employee = employee_res.data
    company_id = employee.get("company_id")
    company_res = (
        supabase.table("companies").select("*").eq("id", company_id).single().execute()
    )
    company = company_res.data if company_res.data else {}
    schedule_res = (
        supabase.table("employee_schedules")
        .select("*")
        .match(
            {
                "employee_id": employee_id,
                "year": year,
                "month": month,
            }
        )
        .maybe_single()
        .execute()
    )
    schedule = schedule_res.data if schedule_res and schedule_res.data else {}
    prev_month = month - 1
    prev_year = year
    if prev_month == 0:
        prev_month = 12
        prev_year -= 1
    cumuls_res = (
        supabase.table("employee_schedules")
        .select("cumuls")
        .match(
            {
                "employee_id": employee_id,
                "year": prev_year,
                "month": prev_month,
            }
        )
        .maybe_single()
        .execute()
    )
    cumuls_precedents: Dict[str, Any] = {}
    if cumuls_res and cumuls_res.data and cumuls_res.data.get("cumuls"):
        cumuls_data = cumuls_res.data.get("cumuls", {})
        cumuls_precedents = (
            cumuls_data.get("cumuls", {}) if isinstance(cumuls_data, dict) else {}
        )
    monthly_inputs_res = (
        supabase.table("monthly_inputs")
        .select("*")
        .match(
            {
                "employee_id": employee_id,
                "year": year,
                "month": month,
            }
        )
        .execute()
    )
    monthly_inputs = monthly_inputs_res.data or []
    last_day = calendar.monthrange(year, month)[1]
    expense_res = (
        supabase.table("expense_reports")
        .select("*")
        .eq("employee_id", employee_id)
        .gte("date", f"{year}-{month:02d}-01")
        .lte("date", f"{year}-{month:02d}-{last_day:02d}")
        .execute()
    )
    expenses = expense_res.data or []
    absences_res = (
        supabase.table("absence_requests")
        .select("*")
        .eq("employee_id", employee_id)
        .eq("status", "validated")
        .execute()
    )
    all_absences = absences_res.data or []
    month_start = f"{year}-{month:02d}-01"
    month_end = f"{year}-{month:02d}-{last_day:02d}"
    absences: List[Dict[str, Any]] = []
    for absence in all_absences:
        selected_days = absence.get("selected_days", [])
        if not selected_days:
            continue
        for day in selected_days:
            if month_start <= day <= month_end:
                absences.append(absence)
                break
    salaire_base = employee.get("salaire_de_base", {})
    if isinstance(salaire_base, str):
        salaire_base = json.loads(salaire_base)
    salaire_base_mensuel = (
        salaire_base.get("valeur", 0) if isinstance(salaire_base, dict) else 0
    )
    duree_hebdo = employee.get("duree_hebdomadaire", 35)
    heures_mensuelles_contrat = round((duree_hebdo * 52) / 12, 2)
    actual_hours = schedule.get("actual_hours", {})
    if isinstance(actual_hours, str):
        actual_hours = json.loads(actual_hours)
    calendrier_reel = (
        actual_hours.get("calendrier_reel", [])
        if isinstance(actual_hours, dict)
        else []
    )
    planned_calendar = schedule.get("planned_calendar", {})
    if isinstance(planned_calendar, str):
        planned_calendar = json.loads(planned_calendar)
    calendrier_prevu = (
        planned_calendar.get("calendrier_prevu", [])
        if isinstance(planned_calendar, dict)
        else []
    )
    heures_travaillees = 0.0
    heures_prevues = 0.0
    detail_jours_reel: List[Dict[str, Any]] = []
    detail_jours_prevu: List[Dict[str, Any]] = []
    for jour in calendrier_reel:
        heures_faites = jour.get("heures_faites", 0) or 0
        type_jour = jour.get("type", "travail")
        date_jour = jour.get("date") or jour.get("jour", "N/A")
        heures_travaillees += heures_faites
        detail_jours_reel.append(
            {"date": date_jour, "type": type_jour, "heures_faites": heures_faites}
        )
    for jour in calendrier_prevu:
        heures_jour = jour.get("heures_prevues", 0) or 0
        type_jour = jour.get("type", "travail")
        date_jour = jour.get("date") or jour.get("jour", "N/A")
        heures_prevues += heures_jour
        detail_jours_prevu.append(
            {"date": date_jour, "type": type_jour, "heures_prevues": heures_jour}
        )
    source_heures = "calendrier_reel"
    if heures_travaillees == 0:
        if heures_prevues > 0:
            heures_travaillees = heures_prevues
            source_heures = "calendrier_prevu"
        else:
            heures_travaillees = heures_mensuelles_contrat
            source_heures = "contrat_mensualise"
    primes_soumises = sum(
        p.get("amount", 0) for p in monthly_inputs if p.get("is_socially_taxed", True)
    )
    primes_non_soumises = sum(
        p.get("amount", 0)
        for p in monthly_inputs
        if not p.get("is_socially_taxed", True)
    )
    detail_primes_soumises = [
        {"name": p.get("name"), "amount": float(p.get("amount", 0))}
        for p in monthly_inputs
        if p.get("is_socially_taxed", True)
    ]
    detail_primes_non_soumises = [
        {"name": p.get("name"), "amount": float(p.get("amount", 0))}
        for p in monthly_inputs
        if not p.get("is_socially_taxed", True)
    ]
    salaire_brut_mois = salaire_base_mensuel + primes_soumises
    composition_brut = {
        "salaire_base_mensuel": round(salaire_base_mensuel, 2),
        "primes_soumises": round(primes_soumises, 2),
        "detail_primes_soumises": detail_primes_soumises,
        "primes_non_soumises": round(primes_non_soumises, 2),
        "detail_primes_non_soumises": detail_primes_non_soumises,
        "salaire_brut_mois": round(salaire_brut_mois, 2),
    }
    heures_remunerees_mois = heures_travaillees
    baremes_res = (
        supabase.table("payroll_config")
        .select("config_key, config_data")
        .eq("is_active", True)
        .execute()
    )
    baremes = {c["config_key"]: c["config_data"] for c in (baremes_res.data or [])}
    smic_data = baremes.get("smic", {})
    smic_horaire = smic_data.get("cas_general", 11.88)
    cotisations_data = baremes.get("cotisations", {}).get("cotisations", [])
    catalogue_cotisations = {c["id"]: c for c in cotisations_data}
    taux_details: Dict[str, float] = {}
    taux_details_explicatifs: Dict[str, Any] = {}
    maladie_taux = catalogue_cotisations.get("securite_sociale_maladie", {}).get(
        "patronal_reduit", 0.07
    )
    taux_details["maladie"] = maladie_taux
    taux_details_explicatifs["maladie"] = {
        "libelle": "Sécurité sociale - Maladie (taux réduit)",
        "valeur": maladie_taux,
        "source": "patronal_reduit de securite_sociale_maladie",
    }
    alloc_fam_taux = catalogue_cotisations.get("allocations_familiales", {}).get(
        "patronal_reduit", 0.0345
    )
    taux_details["allocations_familiales"] = alloc_fam_taux
    taux_details_explicatifs["allocations_familiales"] = {
        "libelle": "Allocations familiales (taux réduit)",
        "valeur": alloc_fam_taux,
        "source": "patronal_reduit de allocations_familiales",
    }
    vieillesse_plaf_taux = catalogue_cotisations.get("retraite_secu_plafond", {}).get(
        "patronal", 0.0855
    )
    taux_details["vieillesse_plafonnee"] = vieillesse_plaf_taux
    taux_details_explicatifs["vieillesse_plafonnee"] = {
        "libelle": "Retraite sécurité sociale (plafonnée)",
        "valeur": vieillesse_plaf_taux,
        "source": "patronal de retraite_secu_plafond",
    }
    vieillesse_deplaf_taux = catalogue_cotisations.get(
        "retraite_secu_deplafond", {}
    ).get("patronal", 0.0202)
    taux_details["vieillesse_deplafonnee"] = vieillesse_deplaf_taux
    taux_details_explicatifs["vieillesse_deplafonnee"] = {
        "libelle": "Retraite sécurité sociale (déplafonnée)",
        "valeur": vieillesse_deplaf_taux,
        "source": "patronal de retraite_secu_deplafond",
    }
    csa_taux = catalogue_cotisations.get("csa", {}).get("patronal", 0.003)
    taux_details["csa"] = csa_taux
    taux_details_explicatifs["csa"] = {
        "libelle": "Contribution Solidarité Autonomie (CSA)",
        "valeur": csa_taux,
        "source": "patronal de csa",
    }
    chomage_taux = catalogue_cotisations.get("assurance_chomage", {}).get(
        "patronal", 0.04
    )
    taux_details["chomage"] = chomage_taux
    taux_details_explicatifs["chomage"] = {
        "libelle": "Assurance Chômage",
        "valeur": chomage_taux,
        "source": "patronal de assurance_chomage",
    }
    retraite_comp_t1_taux = catalogue_cotisations.get("retraite_comp_t1", {}).get(
        "patronal", 0.0472
    )
    taux_details["retraite_comp_t1"] = retraite_comp_t1_taux
    taux_details_explicatifs["retraite_comp_t1"] = {
        "libelle": "Retraite complémentaire T1 (AGIRC-ARRCO)",
        "valeur": retraite_comp_t1_taux,
        "source": "patronal de retraite_comp_t1",
    }
    ceg_t1_taux = catalogue_cotisations.get("ceg_t1", {}).get("patronal", 0.0129)
    taux_details["ceg_t1"] = ceg_t1_taux
    taux_details_explicatifs["ceg_t1"] = {
        "libelle": "Contribution d'Équilibre Général (CEG) T1",
        "valeur": ceg_t1_taux,
        "source": "patronal de ceg_t1",
    }
    effectif = company.get("effectif", 51)
    fnal_taux = catalogue_cotisations.get("fnal", {}).get("patronal", {})
    if isinstance(fnal_taux, dict):
        fnal_valeur = (
            fnal_taux.get("taux_50_et_plus", 0.005)
            if effectif >= 50
            else fnal_taux.get("taux_moins_50", 0.001)
        )
        taux_details["fnal"] = fnal_valeur
        taux_details_explicatifs["fnal"] = {
            "libelle": f"FNAL (effectif: {effectif}, donc taux {'≥50' if effectif >= 50 else '<50'})",
            "valeur": fnal_valeur,
            "source": f"patronal.fnal.taux_{'50_et_plus' if effectif >= 50 else 'moins_50'}",
            "condition": f"effectif {effectif} {'≥' if effectif >= 50 else '<'} 50",
        }
    else:
        fnal_valeur = fnal_taux or 0.005
        taux_details["fnal"] = fnal_valeur
        taux_details_explicatifs["fnal"] = {
            "libelle": "FNAL (taux unique)",
            "valeur": fnal_valeur,
            "source": "patronal de fnal",
        }
    taux_at_mp_pourcentage = company.get("taux_at_mp", 3.1)
    taux_at_mp = taux_at_mp_pourcentage / 100.0
    taux_details["at_mp"] = taux_at_mp
    taux_details_explicatifs["at_mp"] = {
        "libelle": "Accidents du travail et maladies professionnelles (AT/MP)",
        "valeur": taux_at_mp,
        "valeur_pourcentage": taux_at_mp_pourcentage,
        "source": "taux_at_mp de companies (divisé par 100)",
        "note": f"Taux en base: {taux_at_mp_pourcentage}% → {taux_at_mp} en décimal",
    }
    brut_cumule_precedent = cumuls_precedents.get("brut_total", 0.0)
    heures_cumulees_precedent = cumuls_precedents.get("heures_remunerees", 0.0)
    reduction_deja_appliquee = abs(
        cumuls_precedents.get("reduction_generale_patronale", 0.0)
    )
    brut_total_cumule = brut_cumule_precedent + salaire_brut_mois
    heures_total_cumulees = heures_cumulees_precedent + heures_remunerees_mois
    smic_reference_cumule = smic_horaire * heures_total_cumulees
    calcul_coefficient_C_detail: Dict[str, Any] = {}

    # Garde-fou par période : RGDU à partir de 2026, Fillon (RGCP) avant.
    from app.modules.payroll.engine import legal_constants as _lc
    from app.modules.payroll.engine.calcul_reduction_generale import (
        calculer_coefficient_rgdu as _calculer_coefficient_rgdu,
    )

    if year >= _lc.ANNEE_BASCULE_RGDU:
        # --- Branche RGDU (>= 2026) : paramètres scrapables dans payroll_config ---
        rgdu_cfg = baremes.get("reduction_generale", {}) or {}
        tmin = float(rgdu_cfg.get("tmin", 0.02))
        p_expo = float(rgdu_cfg.get("p", 1.75))
        point_sortie = float(rgdu_cfg.get("point_sortie_smic", 3.0))
        tdelta_cfg = rgdu_cfg.get("tdelta", {}) or {}
        tdelta = float(
            tdelta_cfg.get("fnal_50_et_plus", 0.0)
            if effectif >= 50
            else tdelta_cfg.get("fnal_moins_50", 0.0)
        )
        actif = bool(rgdu_cfg) and bool(rgdu_cfg.get("actif", False))
        tmax = round(tmin + tdelta, 4)

        # Affichage : remplacer les taux Fillon par les paramètres RGDU.
        taux_details = {"tmin": tmin, "tdelta": tdelta}
        taux_details_explicatifs = {
            "tmin": {
                "libelle": "Tmin (seuil minimal d'exonération, 2 %)",
                "valeur": tmin,
                "source": "reduction_generale.tmin",
            },
            "tdelta": {
                "libelle": f"Tdelta (FNAL {'≥50' if effectif >= 50 else '<50'} salariés)",
                "valeur": tdelta,
                "source": (
                    "reduction_generale.tdelta."
                    + ("fnal_50_et_plus" if effectif >= 50 else "fnal_moins_50")
                ),
                "condition": f"effectif {effectif} {'≥' if effectif >= 50 else '<'} 50",
            },
            "p": {
                "libelle": "P (exposant de dégressivité)",
                "valeur": p_expo,
                "source": "reduction_generale.p",
            },
        }
        parametre_T = tmax
        calcul_T_detail = {"somme_taux": tmax, "nombre_taux": 2, "verification": tmax}
        seuil_eligibilite = point_sortie * smic_reference_cumule
        seuil_multiplicateur = point_sortie
        formule_C = (
            "C = Tmin + (Tdelta × [ (1/2) × (point_sortie × SMIC / Brut − 1) ]^P)"
        )

        if not actif:
            coefficient_C = 0.0
            reduction_totale_due = 0.0
            montant_reduction_mois = -reduction_deja_appliquee
            eligible = False
            calcul_coefficient_C_detail = {
                "condition": "Dispositif RGDU désactivé (actif = false)",
                "resultat": "Aucune réduction — Coefficient C = 0",
                "reduction_totale": 0,
                "remboursement": f"Remboursement de {reduction_deja_appliquee:.2f} € déjà appliquée",
            }
        else:
            coefficient_C, calcul_coefficient_C_detail = _calculer_coefficient_rgdu(
                brut_total_cumule,
                smic_reference_cumule,
                tmin=tmin,
                tdelta=tdelta,
                p=p_expo,
                point_sortie=point_sortie,
            )
            eligible = coefficient_C > 0
            reduction_totale_due = round(brut_total_cumule * coefficient_C, 2)
            montant_reduction_mois = reduction_totale_due - reduction_deja_appliquee
    else:
        # --- Branche Fillon (RGCP, périodes < 2026), conservée à l'identique ---
        parametre_T = sum(taux_details.values())
        calcul_T_detail = {
            "somme_taux": round(parametre_T, 6),
            "nombre_taux": len(taux_details),
            "verification": round(sum(round(v, 6) for v in taux_details.values()), 6),
        }
        seuil_eligibilite = 1.6 * smic_reference_cumule
        seuil_multiplicateur = 1.6
        formule_C = (
            f"({parametre_T:.6f} / 0.6) × ((1.6 × {smic_reference_cumule:.2f}) "
            f"/ {brut_total_cumule:.2f} - 1)"
        )
        if brut_total_cumule >= seuil_eligibilite:
            coefficient_C = 0.0
            reduction_totale_due = 0.0
            montant_reduction_mois = -reduction_deja_appliquee
            eligible = False
            calcul_coefficient_C_detail = {
                "condition": f"Brut cumulé ({brut_total_cumule:.2f}) >= Seuil 1.6 SMIC ({seuil_eligibilite:.2f})",
                "resultat": "Non éligible - Coefficient C = 0",
                "reduction_totale": 0,
                "remboursement": f"Remboursement de {reduction_deja_appliquee:.2f} € déjà appliquée",
            }
        else:
            ratio_T_06 = parametre_T / 0.6
            ratio_16_smic_brut = seuil_eligibilite / brut_total_cumule
            difference = ratio_16_smic_brut - 1
            coefficient_C_avant_bornage = ratio_T_06 * difference
            coefficient_C = min(max(0, coefficient_C_avant_bornage), parametre_T)
            bornee_inf = coefficient_C_avant_bornage < 0
            bornee_sup = coefficient_C_avant_bornage > parametre_T
            bornee = bornee_inf or bornee_sup
            reduction_totale_due = brut_total_cumule * coefficient_C
            montant_reduction_mois = reduction_totale_due - reduction_deja_appliquee
            eligible = True
            calcul_coefficient_C_detail = {
                "formule_complete": "C = (T / 0.6) × ((1.6 × SMIC_cumulé / Brut_cumulé) - 1)",
                "etape_1": {
                    "calcul": "T / 0.6",
                    "valeur": f"{parametre_T:.6f} / 0.6",
                    "resultat": round(ratio_T_06, 6),
                },
                "etape_2": {
                    "calcul": "1.6 × SMIC_cumulé / Brut_cumulé",
                    "valeur": f"1.6 × {smic_reference_cumule:.2f} / {brut_total_cumule:.2f}",
                    "resultat": round(ratio_16_smic_brut, 6),
                },
                "etape_3": {
                    "calcul": "Ratio - 1",
                    "valeur": f"{ratio_16_smic_brut:.6f} - 1",
                    "resultat": round(difference, 6),
                },
                "etape_4": {
                    "calcul": "(T / 0.6) × (Ratio - 1)",
                    "valeur": f"{ratio_T_06:.6f} × {difference:.6f}",
                    "resultat": round(coefficient_C_avant_bornage, 6),
                    "avant_bornage": True,
                },
                "bornage": {
                    "necessaire": bornee,
                    "bornee_inferieure": bornee_inf,
                    "bornee_superieure": bornee_sup,
                    "avant_bornage": round(coefficient_C_avant_bornage, 6),
                    "apres_bornage": round(coefficient_C, 6),
                    "borne_min": 0,
                    "borne_max": round(parametre_T, 6),
                },
                "coefficient_C_final": round(coefficient_C, 6),
            }
    montant_final = -round(montant_reduction_mois, 2)
    return {
        "result": {
            "libelle": "Réduction générale de cotisations patronales",
            "base": salaire_brut_mois,
            "taux_patronal": round(coefficient_C, 6) if coefficient_C > 0 else None,
            "montant_patronal": montant_final,
            "valeur_cumulative_a_enregistrer": round(reduction_totale_due, 2),
        },
        "employee_data": {
            "id": employee.get("id"),
            "name": f"{employee.get('first_name', '')} {employee.get('last_name', '')}".strip(),
            "statut": employee.get("statut", "Non-Cadre"),
            "job_title": employee.get("job_title", ""),
            "duree_hebdomadaire": duree_hebdo,
            "salaire_base_mensuel": salaire_base_mensuel,
            "hire_date": employee.get("hire_date"),
        },
        "company_data": {
            "name": company.get("company_name", ""),
            "effectif": effectif,
            "taux_at_mp": taux_at_mp,
            "taux_at_mp_pourcentage": taux_at_mp_pourcentage,
        },
        "schedule_data": {
            "heures_prevues": heures_prevues,
            "heures_travaillees": heures_travaillees,
            "heures_remunerees_mois": heures_remunerees_mois,
            "heures_mensuelles_contrat": heures_mensuelles_contrat,
            "calendrier_reel_count": len(calendrier_reel),
            "calendrier_prevu_count": len(calendrier_prevu),
            "source_heures_utilisees": source_heures,
            "detail_jours_reel": detail_jours_reel,
            "detail_jours_prevu": detail_jours_prevu,
            "formule_heures_mensuelles": f"({duree_hebdo} × 52) / 12 = {heures_mensuelles_contrat:.2f}h",
        },
        "monthly_inputs_data": {
            "primes": [
                {
                    "name": p.get("name"),
                    "amount": p.get("amount"),
                    "is_socially_taxed": p.get("is_socially_taxed"),
                }
                for p in monthly_inputs
            ],
            "total_primes_soumises": primes_soumises,
            "total_primes_non_soumises": primes_non_soumises,
        },
        "composition_brut": composition_brut,
        "expenses_data": {
            "count": len(expenses),
            "total_amount": sum(e.get("amount", 0) for e in expenses),
            "expenses": [
                {
                    "date": e.get("date"),
                    "type": e.get("type"),
                    "amount": e.get("amount"),
                    "status": e.get("status"),
                }
                for e in expenses
            ],
        },
        "absences_data": {
            "count": len(absences),
            "types": list(set(a.get("type") for a in absences if a.get("type"))),
        },
        "cumuls_precedents": {
            "brut_total": brut_cumule_precedent,
            "heures_remunerees": heures_cumulees_precedent,
            "reduction_generale_patronale": -reduction_deja_appliquee,
        },
        "calcul_detail": {
            "salaire_brut_mois": round(salaire_brut_mois, 2),
            "heures_remunerees_mois": round(heures_remunerees_mois, 2),
            "brut_total_cumule": round(brut_total_cumule, 2),
            "heures_total_cumulees": round(heures_total_cumulees, 2),
            "smic_horaire": smic_horaire,
            "smic_reference_cumule": round(smic_reference_cumule, 2),
            "seuil_eligibilite_1_6_smic": round(seuil_eligibilite, 2),
            "ratio_brut_smic": round(brut_total_cumule / smic_reference_cumule, 4)
            if smic_reference_cumule > 0
            else 0,
            "eligible": eligible,
            "parametre_T": round(parametre_T, 6),
            "taux_details": {k: round(v, 6) for k, v in taux_details.items()},
            "taux_details_explicatifs": taux_details_explicatifs,
            "calcul_T_detail": calcul_T_detail,
            "coefficient_C": round(coefficient_C, 6),
            "formule_C": formule_C,
            "calcul_coefficient_C_detail": calcul_coefficient_C_detail,
            "reduction_totale_due": round(reduction_totale_due, 2),
            "reduction_deja_appliquee": round(reduction_deja_appliquee, 2),
            "montant_reduction_mois": round(montant_reduction_mois, 2),
            "calcul_cumuls": {
                "brut_precedent": round(brut_cumule_precedent, 2),
                "brut_mois": round(salaire_brut_mois, 2),
                "brut_total": round(brut_total_cumule, 2),
                "formule": f"{brut_cumule_precedent:.2f} + {salaire_brut_mois:.2f} = {brut_total_cumule:.2f}",
            },
            "calcul_heures": {
                "heures_precedentes": round(heures_cumulees_precedent, 2),
                "heures_mois": round(heures_remunerees_mois, 2),
                "heures_total": round(heures_total_cumulees, 2),
                "formule": f"{heures_cumulees_precedent:.2f} + {heures_remunerees_mois:.2f} = {heures_total_cumulees:.2f}",
            },
            "calcul_smic": {
                "smic_horaire": smic_horaire,
                "heures_cumulees": round(heures_total_cumulees, 2),
                "smic_reference": round(smic_reference_cumule, 2),
                "formule": f"{smic_horaire:.2f} × {heures_total_cumulees:.2f} = {smic_reference_cumule:.2f}",
            },
            "calcul_seuil": {
                "smic_reference": round(smic_reference_cumule, 2),
                "seuil_1_6": round(seuil_eligibilite, 2),
                "formule": f"{seuil_multiplicateur} × {smic_reference_cumule:.2f} = {seuil_eligibilite:.2f}",
            },
            "verification_eligibilite": {
                "brut_cumule": round(brut_total_cumule, 2),
                "seuil": round(seuil_eligibilite, 2),
                "comparaison": f"{brut_total_cumule:.2f} {'>=' if brut_total_cumule >= seuil_eligibilite else '<'} {seuil_eligibilite:.2f}",
                "eligible": eligible,
                "ratio": round(brut_total_cumule / smic_reference_cumule, 6)
                if smic_reference_cumule > 0
                else 0,
            },
            "calcul_reduction_finale": {
                "reduction_totale_due": round(reduction_totale_due, 2),
                "formule_totale": f"{brut_total_cumule:.2f} × {coefficient_C:.6f} = {reduction_totale_due:.2f}",
                "reduction_deja_appliquee": round(reduction_deja_appliquee, 2),
                "montant_mois": round(montant_reduction_mois, 2),
                "formule_mois": f"{reduction_totale_due:.2f} - {reduction_deja_appliquee:.2f} = {montant_reduction_mois:.2f}",
                "montant_final_arrondi": montant_final,
            },
        },
        "input_data": {"employee_id": employee_id, "month": month, "year": year},
        "error": None,
    }
