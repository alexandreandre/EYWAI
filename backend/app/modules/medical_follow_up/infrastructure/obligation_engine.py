# app/modules/medical_follow_up/infrastructure/obligation_engine.py
"""
Moteur de règles pour les obligations de suivi médical (VIP, SIR, reprise, mi-carrière, demande).

Logique recopiée depuis le legacy (services/medical_follow_up_service) pour autonomie du module.
Utilise uniquement app.modules.medical_follow_up.infrastructure.database.get_supabase().
Comportement strictement identique.
"""

from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from app.modules.medical_follow_up.infrastructure.database import get_supabase

# Périodicités et seuils (alignés migration 35 / legacy)
VIP_PERIOD_YEARS = 5
SIR_INTERMEDIATE_YEARS = 2
SIR_RENEWAL_YEARS = 4
REPRISE_DAYS_AFTER_RETURN = 8
REPRISE_ABSENCE_TYPES = [
    "arret_maternite",
    "arret_at",
    "arret_maladie_pro",
    "arret_maladie",
]
REPRISE_MIN_DAYS_AT_MP = 30
REPRISE_MIN_DAYS_MALADIE = 60


def _parse_date(d: Any) -> Optional[date]:
    if d is None:
        return None
    if isinstance(d, date):
        return d
    if isinstance(d, str):
        try:
            return date.fromisoformat(d[:10])
        except (ValueError, TypeError):
            return None
    return None


def _get_employee_collective_agreement_idcc(
    supabase: Any, employee_id: str
) -> Optional[str]:
    emp = (
        supabase.table("employees")
        .select("collective_agreement_id, company_id")
        .eq("id", employee_id)
        .maybe_single()
        .execute()
    )
    if not emp or not emp.data:
        return None
    cc_id = emp.data.get("collective_agreement_id")
    if cc_id:
        cat = (
            supabase.table("collective_agreements_catalog")
            .select("idcc")
            .eq("id", cc_id)
            .maybe_single()
            .execute()
        )
        if cat and cat.data and cat.data.get("idcc") is not None:
            return str(cat.data["idcc"])
    company_id = emp.data.get("company_id")
    if not company_id:
        return None
    cca = (
        supabase.table("company_collective_agreements")
        .select("collective_agreement_id")
        .eq("company_id", company_id)
        .limit(1)
        .execute()
    )
    if not cca or not cca.data:
        return None
    agg_id = cca.data[0].get("collective_agreement_id")
    if not agg_id:
        return None
    cat = (
        supabase.table("collective_agreements_catalog")
        .select("idcc")
        .eq("id", agg_id)
        .maybe_single()
        .execute()
    )
    if cat and cat.data and cat.data.get("idcc") is not None:
        return str(cat.data["idcc"])
    return None


def _get_vip_period_years(employee_id: str) -> int:
    return VIP_PERIOD_YEARS


def _get_absence_return_dates_for_reprise(
    supabase: Any, employee_id: str
) -> List[Dict[str, Any]]:
    today = date.today()
    req = (
        supabase.table("absence_requests")
        .select("id, type, selected_days, status")
        .eq("employee_id", employee_id)
        .eq("status", "validated")
        .in_("type", REPRISE_ABSENCE_TYPES)
        .execute()
    )
    items = []
    for r in req.data or []:
        days = r.get("selected_days") or []
        if not days:
            continue
        try:
            day_dates = [
                d if isinstance(d, date) else date.fromisoformat(str(d)[:10])
                for d in days
            ]
        except (ValueError, TypeError):
            continue
        end_date = max(day_dates)
        if end_date >= today:
            continue
        n_days = len(day_dates)
        abs_type = r.get("type") or ""
        if abs_type == "arret_maladie":
            if n_days < REPRISE_MIN_DAYS_MALADIE:
                continue
        elif abs_type in ("arret_at", "arret_maladie_pro", "arret_maternite"):
            if n_days < REPRISE_MIN_DAYS_AT_MP:
                continue
        due_date = end_date + timedelta(days=REPRISE_DAYS_AFTER_RETURN)
        items.append(
            {
                "end_date": end_date,
                "due_date": due_date,
                "absence_type": abs_type,
                "absence_request_id": r.get("id"),
            }
        )
    return items


def _existing_obligations(
    supabase: Any, company_id: str, employee_id: str
) -> List[Dict[str, Any]]:
    req = (
        supabase.table("medical_follow_up_obligations")
        .select("*")
        .eq("company_id", company_id)
        .eq("employee_id", employee_id)
        .neq("status", "annulee")
        .execute()
    )
    return list(req.data or [])


def _dedupe_key(
    visit_type: str,
    trigger_type: str,
    due_date: date,
    request_date: Optional[date] = None,
):
    if visit_type == "demande" and request_date:
        return (visit_type, trigger_type, request_date.isoformat())
    return (visit_type, trigger_type, due_date.isoformat())


def compute_obligations_for_employee(
    company_id: str, employee_id: str
) -> List[Dict[str, Any]]:
    """
    Calcule et upsert les obligations de suivi médical pour un employé.
    Comportement identique au legacy (sans dépendance à services/*).
    """
    supabase = get_supabase()
    emp = (
        supabase.table("employees")
        .select(
            "id, company_id, hire_date, date_naissance, job_title, employment_status, "
            "is_poste_sir, is_travail_nuit, collective_agreement_id"
        )
        .eq("id", employee_id)
        .eq("company_id", company_id)
        .maybe_single()
        .execute()
    )
    if not emp or not emp.data:
        return []

    data = emp.data
    employment_status = (data.get("employment_status") or "actif").strip().lower()
    if employment_status not in ("actif", "en_sortie"):
        return []

    hire_date = _parse_date(data.get("hire_date"))
    birth_date = _parse_date(data.get("date_naissance"))
    is_poste_sir = data.get("is_poste_sir") is True
    is_travail_nuit = data.get("is_travail_nuit") is True
    today = date.today()

    idcc = _get_employee_collective_agreement_idcc(supabase, employee_id)
    rule_source = "convention" if idcc else "legal"

    existing = _existing_obligations(supabase, company_id, employee_id)
    existing_keys = {
        _dedupe_key(
            o.get("visit_type"),
            o.get("trigger_type"),
            _parse_date(o.get("due_date")) or today,
            _parse_date(o.get("request_date")),
        )
        for o in existing
    }

    to_insert: List[Dict[str, Any]] = []
    to_update: List[tuple] = []

    if is_poste_sir and hire_date:
        due = hire_date
        key = _dedupe_key("aptitude_sir_avant_affectation", "poste_sir", due)
        if key not in existing_keys:
            to_insert.append(
                {
                    "company_id": company_id,
                    "employee_id": employee_id,
                    "visit_type": "aptitude_sir_avant_affectation",
                    "trigger_type": "poste_sir",
                    "due_date": due.isoformat(),
                    "priority": 1,
                    "status": "a_faire",
                    "rule_source": rule_source,
                    "collective_agreement_idcc": idcc,
                }
            )
            existing_keys.add(key)
        else:
            for o in existing:
                if o.get("visit_type") == "aptitude_sir_avant_affectation":
                    to_update.append((o["id"], {"due_date": due.isoformat()}))
                    break

    is_mineur = birth_date and (today - birth_date).days < 18 * 365
    if (is_mineur or is_travail_nuit) and hire_date:
        due = hire_date
        key = _dedupe_key("vip_avant_affectation_mineur_nuit", "nuit_mineur", due)
        if key not in existing_keys:
            to_insert.append(
                {
                    "company_id": company_id,
                    "employee_id": employee_id,
                    "visit_type": "vip_avant_affectation_mineur_nuit",
                    "trigger_type": "nuit_mineur",
                    "due_date": due.isoformat(),
                    "priority": 1,
                    "status": "a_faire",
                    "rule_source": rule_source,
                    "collective_agreement_idcc": idcc,
                }
            )
            existing_keys.add(key)

    for item in _get_absence_return_dates_for_reprise(supabase, employee_id):
        due = item["due_date"]
        key = _dedupe_key("reprise", "arret_long", due)
        if key not in existing_keys:
            to_insert.append(
                {
                    "company_id": company_id,
                    "employee_id": employee_id,
                    "visit_type": "reprise",
                    "trigger_type": "arret_long",
                    "due_date": due.isoformat(),
                    "priority": 1,
                    "status": "a_faire",
                    "rule_source": "legal",
                    "justification": f"Reprise après {item['absence_type']}",
                }
            )
            existing_keys.add(key)

    if birth_date:
        birth_45 = date(birth_date.year + 45, birth_date.month, birth_date.day)
        if today >= birth_45:
            due = birth_45
            key = _dedupe_key("mi_carriere_45", "age_45", due)
            if key not in existing_keys:
                to_insert.append(
                    {
                        "company_id": company_id,
                        "employee_id": employee_id,
                        "visit_type": "mi_carriere_45",
                        "trigger_type": "age_45",
                        "due_date": due.isoformat(),
                        "priority": 2,
                        "status": "a_faire",
                        "rule_source": rule_source,
                        "collective_agreement_idcc": idcc,
                    }
                )
                existing_keys.add(key)

    vip_years = _get_vip_period_years(employee_id)
    last_vip = (
        supabase.table("medical_follow_up_obligations")
        .select("completed_date, due_date")
        .eq("employee_id", employee_id)
        .eq("visit_type", "vip")
        .eq("status", "realisee")
        .order("completed_date", desc=True)
        .limit(1)
        .execute()
    )
    if last_vip.data and last_vip.data[0].get("completed_date"):
        last_d = _parse_date(last_vip.data[0]["completed_date"])
        if last_d:
            next_due = last_d.replace(year=last_d.year + vip_years)
            key = _dedupe_key("vip", "periodicite_vip", next_due)
            if key not in existing_keys:
                to_insert.append(
                    {
                        "company_id": company_id,
                        "employee_id": employee_id,
                        "visit_type": "vip",
                        "trigger_type": "periodicite_vip",
                        "due_date": next_due.isoformat(),
                        "priority": 2,
                        "status": "a_faire",
                        "rule_source": rule_source,
                        "collective_agreement_idcc": idcc,
                    }
                )
                existing_keys.add(key)
    elif hire_date:
        next_due = hire_date.replace(year=hire_date.year + vip_years)
        if next_due > today:
            key = _dedupe_key("vip", "periodicite_vip", next_due)
            if key not in existing_keys:
                to_insert.append(
                    {
                        "company_id": company_id,
                        "employee_id": employee_id,
                        "visit_type": "vip",
                        "trigger_type": "embauche",
                        "due_date": next_due.isoformat(),
                        "priority": 2,
                        "status": "a_faire",
                        "rule_source": rule_source,
                        "collective_agreement_idcc": idcc,
                    }
                )
                existing_keys.add(key)

    sir_years = SIR_RENEWAL_YEARS
    last_sir = (
        supabase.table("medical_follow_up_obligations")
        .select("completed_date, due_date")
        .eq("employee_id", employee_id)
        .eq("visit_type", "sir")
        .eq("status", "realisee")
        .order("completed_date", desc=True)
        .limit(1)
        .execute()
    )
    if last_sir.data and last_sir.data[0].get("completed_date"):
        last_d = _parse_date(last_sir.data[0]["completed_date"])
        if last_d:
            next_due = last_d.replace(year=last_d.year + sir_years)
            key = _dedupe_key("sir", "periodicite_sir", next_due)
            if key not in existing_keys:
                to_insert.append(
                    {
                        "company_id": company_id,
                        "employee_id": employee_id,
                        "visit_type": "sir",
                        "trigger_type": "periodicite_sir",
                        "due_date": next_due.isoformat(),
                        "priority": 2,
                        "status": "a_faire",
                        "rule_source": rule_source,
                        "collective_agreement_idcc": idcc,
                    }
                )
                existing_keys.add(key)
    elif is_poste_sir and hire_date:
        next_due = hire_date.replace(year=hire_date.year + SIR_INTERMEDIATE_YEARS)
        if next_due > today:
            key = _dedupe_key("sir", "poste_sir", next_due)
            if key not in existing_keys:
                to_insert.append(
                    {
                        "company_id": company_id,
                        "employee_id": employee_id,
                        "visit_type": "sir",
                        "trigger_type": "poste_sir",
                        "due_date": next_due.isoformat(),
                        "priority": 2,
                        "status": "a_faire",
                        "rule_source": rule_source,
                        "collective_agreement_idcc": idcc,
                    }
                )
                existing_keys.add(key)

    for row in to_insert:
        supabase.table("medical_follow_up_obligations").insert(row).execute()
    for ob_id, payload in to_update:
        supabase.table("medical_follow_up_obligations").update(payload).eq(
            "id", ob_id
        ).execute()

    req = (
        supabase.table("medical_follow_up_obligations")
        .select("*")
        .eq("company_id", company_id)
        .eq("employee_id", employee_id)
        .neq("status", "annulee")
        .order("priority")
        .order("due_date")
        .execute()
    )
    return list(req.data or [])
