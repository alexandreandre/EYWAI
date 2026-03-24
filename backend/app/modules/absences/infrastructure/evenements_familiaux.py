"""
Calcul des droits aux événements familiaux selon la convention collective.

Logique migrée depuis services/evenements_familiaux.py pour autonomie du module.
Utilise uniquement app.core.database (aucun import legacy).
"""
from datetime import date
from typing import Any, Dict, List, Optional

from app.core.database import supabase


def get_employee_collective_agreement(employee_id: str) -> Optional[str]:
    """
    Retourne l'UUID de la convention collective applicable à l'employé.
    Priorité: 1) employees.collective_agreement_id  2) première CC assignée à l'entreprise
    """
    emp = (
        supabase.table("employees")
        .select("collective_agreement_id, company_id")
        .eq("id", employee_id)
        .maybe_single()
        .execute()
    )
    if not emp or not emp.data:
        emp = (
            supabase.table("employees")
            .select("collective_agreement_id, company_id")
            .eq("user_id", employee_id)
            .maybe_single()
            .execute()
        )
    if not emp or not emp.data:
        return None

    cc_id = emp.data.get("collective_agreement_id")
    if cc_id:
        return cc_id

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
    if cca and cca.data and len(cca.data) > 0:
        return cca.data[0]["collective_agreement_id"]
    return None


def get_quota_evenement(
    employee_id: str, event_code: str
) -> Optional[Dict[str, Any]]:
    """
    Retourne le quota pour un événement donné selon la CC de l'employé.
    Retourne {duree_jours, type_jours, condition_anciennete_jours} ou None.
    """
    cc_id = get_employee_collective_agreement(employee_id)
    if not cc_id:
        return None

    override = (
        supabase.table("cc_evenements_familiaux")
        .select("duree_jours, type_jours, condition_anciennete_jours")
        .eq("collective_agreement_id", cc_id)
        .eq("event_code", event_code)
        .maybe_single()
        .execute()
    )
    if override and override.data:
        return override.data

    ref = (
        supabase.table("evenements_familiaux_reference")
        .select("duree_legale_jours, type_jours_legal")
        .eq("code", event_code)
        .maybe_single()
        .execute()
    )
    if ref and ref.data:
        return {
            "duree_jours": ref.data["duree_legale_jours"],
            "type_jours": ref.data["type_jours_legal"],
            "condition_anciennete_jours": None,
        }
    return None


def get_solde_evenement(
    employee_id: str,
    event_code: str,
    hire_date: Optional[date] = None,
) -> Dict[str, Any]:
    """
    Retourne le solde restant pour un événement donné.
    solde_restant = quota - jours déjà pris (validated) pour ce event_subtype.
    """
    quota_info = get_quota_evenement(employee_id, event_code)
    if not quota_info:
        return {
            "quota": 0,
            "taken": 0,
            "solde_restant": 0,
            "type_jours": "JO",
            "condition_ok": False,
        }

    duree = quota_info["duree_jours"]
    type_jours = quota_info.get("type_jours") or "JO"
    cond_anciennete = quota_info.get("condition_anciennete_jours")

    if cond_anciennete and hire_date:
        days_since_hire = (date.today() - hire_date).days
        if days_since_hire < cond_anciennete:
            return {
                "quota": 0,
                "taken": 0,
                "solde_restant": 0,
                "type_jours": type_jours,
                "condition_ok": False,
            }

    reqs = (
        supabase.table("absence_requests")
        .select("selected_days")
        .eq("employee_id", employee_id)
        .eq("type", "evenement_familial")
        .eq("event_subtype", event_code)
        .eq("status", "validated")
        .execute()
    )
    taken = 0
    for r in (reqs.data if reqs else []) or []:
        days = r.get("selected_days") or []
        taken += len(days)

    cycles_completed = taken // duree if duree > 0 else 0
    remainder = taken % duree if duree > 0 else 0
    solde = duree - remainder
    return {
        "quota": duree,
        "taken": taken,
        "solde_restant": solde,
        "type_jours": type_jours,
        "condition_ok": True,
        "cycles_completed": cycles_completed,
    }


def get_events_disponibles(employee_id: str) -> List[Dict[str, Any]]:
    """
    Retourne la liste des événements familiaux disponibles pour l'employé,
    avec libellé, quota et solde restant.
    """
    emp = (
        supabase.table("employees")
        .select("hire_date")
        .eq("id", employee_id)
        .maybe_single()
        .execute()
    )
    hire_date = None
    if emp and emp.data and emp.data.get("hire_date"):
        h = emp.data["hire_date"]
        hire_date = (
            date.fromisoformat(h) if isinstance(h, str) else h
        )

    cc_id = get_employee_collective_agreement(employee_id)
    if not cc_id:
        return []

    overrides = (
        supabase.table("cc_evenements_familiaux")
        .select(
            "event_code, duree_jours, type_jours, condition_anciennete_jours"
        )
        .eq("collective_agreement_id", cc_id)
        .execute()
    )
    refs = (
        supabase.table("evenements_familiaux_reference")
        .select("code, libelle, duree_legale_jours, type_jours_legal, ordre_affichage")
        .order("ordre_affichage")
        .execute()
    )
    ref_map = {r["code"]: r for r in (refs.data if refs else []) or []}
    override_map = {
        o["event_code"]: o for o in (overrides.data if overrides else []) or []
    }

    result = []
    seen_codes = set()
    for ref in (refs.data if refs else []) or []:
        code = ref["code"]
        if code in seen_codes:
            continue
        seen_codes.add(code)
        ov = override_map.get(code)
        if ov:
            duree = ov["duree_jours"]
            type_j = ov.get("type_jours") or "JO"
            cond = ov.get("condition_anciennete_jours")
        else:
            duree = ref["duree_legale_jours"]
            type_j = ref.get("type_jours_legal") or "JO"
            cond = None

        if cond and hire_date:
            days_since_hire = (date.today() - hire_date).days
            if days_since_hire < cond:
                continue

        solde_data = get_solde_evenement(employee_id, code, hire_date)
        result.append({
            "code": code,
            "libelle": ref["libelle"],
            "duree_jours": duree,
            "type_jours": type_j,
            "quota": duree,
            "solde_restant": solde_data["solde_restant"],
            "taken": solde_data["taken"],
            "cycles_completed": solde_data.get("cycles_completed", 0),
        })
    return result
