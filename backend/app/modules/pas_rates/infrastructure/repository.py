"""Persistance Supabase — taux de prélèvement à la source."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.core.database import get_supabase_admin_client
from app.core.logging import get_logger

logger = get_logger("modules.pas_rates.repository")

RATES = "employee_pas_rates"
EMPLOYEES = "employees"

_EMPLOYEE_FIELDS = (
    "id,last_name,first_name,matricule,nir,company_id,employment_status,"
    "hire_date,specificites_paie"
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def lister_salaries(company_id: str, inclure_partis: bool = False) -> List[Dict[str, Any]]:
    """Les salariés d'une société, actifs par défaut."""
    client = get_supabase_admin_client()
    query = client.table(EMPLOYEES).select(_EMPLOYEE_FIELDS).eq("company_id", company_id)
    if not inclure_partis:
        query = query.in_("employment_status", ["actif", "en_sortie"])
    rows: List[Dict[str, Any]] = []
    start = 0
    page = 1000
    while True:
        resp = query.range(start, start + page - 1).execute()
        lot = resp.data or []
        rows.extend(lot)
        if len(lot) < page:
            break
        start += page
    return rows


def get_salarie(employee_id: str) -> Optional[Dict[str, Any]]:
    resp = (
        get_supabase_admin_client()
        .table(EMPLOYEES)
        .select(_EMPLOYEE_FIELDS)
        .eq("id", employee_id)
        .limit(1)
        .execute()
    )
    return resp.data[0] if resp.data else None


def dernier_taux_par_salarie(company_id: str) -> Dict[str, Dict[str, Any]]:
    """Pour chaque salarié, l'entrée d'historique de période la plus récente."""
    resp = (
        get_supabase_admin_client()
        .table(RATES)
        .select("*")
        .eq("company_id", company_id)
        .order("periode", desc=True)
        .order("applied_at", desc=True)
        .execute()
    )
    out: Dict[str, Dict[str, Any]] = {}
    for row in resp.data or []:
        out.setdefault(str(row.get("employee_id")), row)
    return out


def historique_salarie(employee_id: str) -> List[Dict[str, Any]]:
    resp = (
        get_supabase_admin_client()
        .table(RATES)
        .select("*")
        .eq("employee_id", employee_id)
        .order("periode", desc=True)
        .order("applied_at", desc=True)
        .execute()
    )
    return resp.data or []


def enregistrer_taux(entries: List[Dict[str, Any]]) -> int:
    """Écrit l'historique. Rejouer le même fichier ne duplique rien."""
    if not entries:
        return 0
    resp = (
        get_supabase_admin_client()
        .table(RATES)
        .upsert(entries, on_conflict="employee_id,periode,source")
        .execute()
    )
    return len(resp.data or [])


def maj_taux_courant(
    employee_id: str,
    taux: float,
    type_taux: Optional[str],
    identifiant_taux: Optional[str],
    periode: str,
) -> None:
    """Met à jour le bloc lu par le moteur de paie, sans toucher au reste.

    On passe par une lecture puis une écriture ciblée plutôt que par
    `update_employee` : ce dernier fusionne tout `specificites_paie` et déclenche
    des effets de bord (alertes RIB, complétude d'onboarding) sans rapport avec
    un taux d'imposition.
    """
    client = get_supabase_admin_client()
    actuel = get_salarie(employee_id) or {}
    specificites = actuel.get("specificites_paie")
    if not isinstance(specificites, dict):
        specificites = {}
    bloc = specificites.get("prelevement_a_la_source")
    if not isinstance(bloc, dict):
        bloc = {}

    bloc = dict(bloc)
    bloc["taux"] = round(float(taux), 4)
    bloc["periode"] = periode
    if type_taux:
        bloc["type_taux"] = type_taux
    if identifiant_taux:
        bloc["identifiant_taux"] = identifiant_taux
    # Un taux personnalisé nul reste un taux : la case « personnalisé » de la
    # fiche salarié doit rester cochée pour ne pas laisser croire à une absence.
    bloc["is_personnalise"] = True

    specificites = dict(specificites)
    specificites["prelevement_a_la_source"] = bloc

    client.table(EMPLOYEES).update(
        {"specificites_paie": specificites, "updated_at": _now_iso()}
    ).eq("id", employee_id).execute()
