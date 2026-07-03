"""
Repository des plans de calendriers horaires (company_schedule_plans) et
accès lecture aux modèles de semaine + résolution des salariés d'une portée.

Pattern Supabase identique aux repositories modulation/schedules existants.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.core.database import supabase

_PLANS = "company_schedule_plans"
_TEMPLATES = "company_week_schedule_templates"


# ----- company_schedule_plans (CRUD) -----


def list_plans(company_id: str, *, active_only: bool = True) -> List[Dict[str, Any]]:
    q = (
        supabase.table(_PLANS)
        .select("*")
        .eq("company_id", company_id)
        .order("created_at", desc=True)
    )
    if active_only:
        q = q.eq("is_active", True)
    resp = q.execute()
    return resp.data or []


def find_plan_by_name(company_id: str, name: str) -> Optional[Dict[str, Any]]:
    resp = (
        supabase.table(_PLANS)
        .select("*")
        .eq("company_id", company_id)
        .eq("name", name)
        .limit(1)
        .execute()
    )
    rows = resp.data or []
    return rows[0] if rows else None


def get_plan(company_id: str, plan_id: str) -> Optional[Dict[str, Any]]:
    resp = (
        supabase.table(_PLANS)
        .select("*")
        .eq("company_id", company_id)
        .eq("id", plan_id)
        .limit(1)
        .execute()
    )
    rows = resp.data or []
    return rows[0] if rows else None


def create_plan(company_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    row = {
        **payload,
        "company_id": company_id,
        "created_at": now,
        "updated_at": now,
    }
    resp = supabase.table(_PLANS).insert(row).execute()
    return (resp.data or [{}])[0]


def update_plan(
    company_id: str, plan_id: str, payload: Dict[str, Any]
) -> Dict[str, Any]:
    row = {**payload, "updated_at": datetime.now(timezone.utc).isoformat()}
    supabase.table(_PLANS).update(row).eq("company_id", company_id).eq(
        "id", plan_id
    ).execute()
    return get_plan(company_id, plan_id) or {}


def delete_plan(company_id: str, plan_id: str) -> None:
    supabase.table(_PLANS).update(
        {"is_active": False, "updated_at": datetime.now(timezone.utc).isoformat()}
    ).eq("company_id", company_id).eq("id", plan_id).execute()


# ----- modèles de semaine (lecture pour la génération) -----


def get_templates_by_ids(company_id: str, ids: List[str]) -> Dict[str, Dict[str, Any]]:
    if not ids:
        return {}
    resp = (
        supabase.table(_TEMPLATES)
        .select("*")
        .eq("company_id", company_id)
        .in_("id", list(dict.fromkeys(ids)))
        .execute()
    )
    return {str(row["id"]): row for row in (resp.data or [])}


def find_template_by_name(company_id: str, name: str) -> Optional[Dict[str, Any]]:
    resp = (
        supabase.table(_TEMPLATES)
        .select("*")
        .eq("company_id", company_id)
        .eq("name", name)
        .eq("is_active", True)
        .limit(1)
        .execute()
    )
    rows = resp.data or []
    return rows[0] if rows else None


# ----- résolution des salariés d'une portée -----


def resolve_scope_employees(
    company_id: str,
    scope_type: str,
    scope_ref: Optional[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Retourne les salariés actifs d'une portée : {id, statut, first_name, last_name, team_id, service_id}."""
    scope_ref = scope_ref or {}
    select = "id, statut, first_name, last_name, team_id, service_id"

    if scope_type == "employees":
        ids = [str(x) for x in (scope_ref.get("employee_ids") or [])]
        if not ids:
            return []
        out: List[Dict[str, Any]] = []
        for i in range(0, len(ids), 40):
            batch = ids[i : i + 40]
            resp = (
                supabase.table("employees")
                .select(select)
                .eq("company_id", company_id)
                .in_("id", batch)
                .execute()
            )
            out.extend(resp.data or [])
        return out

    q = (
        supabase.table("employees")
        .select(select)
        .eq("company_id", company_id)
        .eq("employment_status", "actif")
    )
    if scope_type == "team" and scope_ref.get("team_id"):
        q = q.eq("team_id", str(scope_ref["team_id"]))
    elif scope_type == "service" and scope_ref.get("service_id"):
        q = q.eq("service_id", str(scope_ref["service_id"]))
    resp = q.execute()
    return resp.data or []


def find_employees_by_name(company_id: str, full_names: List[str]) -> Dict[str, str]:
    """Mappe un nom complet « Prénom NOM » → employee_id (best-effort, pour les presets)."""
    resp = (
        supabase.table("employees")
        .select("id, first_name, last_name")
        .eq("company_id", company_id)
        .execute()
    )
    index: Dict[str, str] = {}
    for row in resp.data or []:
        fn = (row.get("first_name") or "").strip()
        ln = (row.get("last_name") or "").strip()
        full = f"{fn} {ln}".strip().lower()
        if full:
            index[full] = str(row["id"])
    out: Dict[str, str] = {}
    for name in full_names:
        key = name.strip().lower()
        if key in index:
            out[name] = index[key]
    return out
