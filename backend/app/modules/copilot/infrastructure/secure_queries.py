"""
Adaptateur de requêtes sécurisées pour le catalogue d'outils Copilot.

Invariants de sécurité (fail-closed) :
- CHAQUE fonction publique exige un ``company_id: str`` serveur non vide
  (positionnel) : il ne provient JAMAIS du LLM ;
- CHAQUE requête directe est filtrée sur ``company_id`` avant exécution : il n'y
  a jamais de requête sans filtre entreprise ;
- les tables réellement utilisées (``employees``, ``absence_requests``,
  ``shifts``) possèdent toutes une colonne ``company_id`` ; le scoping est donc
  direct. Les agrégats paie et indicateurs RH délèguent à des services déjà
  scopés par entreprise ;
- aucune chaîne SQL, nom de table ou identifiant de périmètre issu du LLM n'est
  utilisé : les arguments LLM ne servent qu'à des filtres métier restreints.
"""

from __future__ import annotations

from datetime import date, timedelta
from difflib import SequenceMatcher
from typing import Any

from app.core.database import get_supabase_client
from app.modules.payroll.application.analytics_queries import (
    get_payroll_analytics_summary,
)
from app.modules.dashboard.application.service import build_analytics_avances


def _require_company_id(company_id: Any) -> str:
    """Garantit un company_id serveur exploitable ; sinon échoue (fail-closed)."""
    if not isinstance(company_id, str) or not company_id.strip():
        raise ValueError(
            "company_id serveur obligatoire et non vide pour toute requête Copilot."
        )
    return company_id


def _current_period() -> str:
    today = date.today()
    return f"{today.year}-{today.month:02d}"


def _resolve_period(raw: Any) -> str:
    """Valide une période ``YYYY-MM`` fournie en argument, sinon période courante."""
    if isinstance(raw, str) and len(raw) == 7 and raw[4] == "-":
        year, _, month = raw.partition("-")
        if year.isdigit() and month.isdigit() and 1 <= int(month) <= 12:
            return raw
    return _current_period()


def _resolve_date_range(filters: dict[str, Any]) -> tuple[str, str]:
    """Renvoie une plage ``(date_start, date_end)`` ISO, par défaut la semaine courante.

    Une plage temporelle est TOUJOURS renvoyée : la requête planning n'est jamais
    exécutée sans borne de dates.
    """
    filters = filters or {}
    start = filters.get("date_start")
    end = filters.get("date_end")
    if _is_iso_date(start) and _is_iso_date(end) and str(start) <= str(end):
        return str(start)[:10], str(end)[:10]

    today = date.today()
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    return monday.isoformat(), sunday.isoformat()


def _is_iso_date(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        date.fromisoformat(value[:10])
        return True
    except ValueError:
        return False


def _coerce_limit(raw: Any, *, default: int, maximum: int) -> int:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return default
    if value < 1:
        return default
    return min(value, maximum)


# --- employees (company_id présent) ---


def count_employees(company_id: str, filters: dict[str, Any]) -> dict[str, Any]:
    """Compte les salariés de l'entreprise, filtre optionnel sur le statut."""
    company_id = _require_company_id(company_id)
    filters = filters or {}
    query = (
        get_supabase_client()
        .table("employees")
        .select("id", count="exact")
        .eq("company_id", company_id)
    )
    status = filters.get("employment_status")
    if status:
        query = query.eq("employment_status", str(status))
    response = query.execute()
    return {"count": int(response.count or 0)}


def search_employees(company_id: str, filters: dict[str, Any]) -> dict[str, Any]:
    """Recherche des salariés par nom, strictement dans l'entreprise active."""
    company_id = _require_company_id(company_id)
    filters = filters or {}
    name = str(filters.get("name") or "").strip().lower()
    limit = _coerce_limit(filters.get("limit"), default=10, maximum=25)

    query = (
        get_supabase_client()
        .table("employees")
        .select("id, first_name, last_name, job_title, employment_status")
        .eq("company_id", company_id)
    )
    status = filters.get("employment_status")
    if status:
        query = query.eq("employment_status", str(status))
    rows = query.execute().data or []

    if name:
        rows = _rank_by_name(rows, name)

    matches = rows[:limit]
    return {"employees": matches, "count": len(matches)}


def _rank_by_name(rows: list[dict[str, Any]], name: str) -> list[dict[str, Any]]:
    scored: list[tuple[float, dict[str, Any]]] = []
    for row in rows:
        first = str(row.get("first_name") or "").lower()
        last = str(row.get("last_name") or "").lower()
        full = f"{first} {last}".strip()
        candidates = [full, first, last, f"{last} {first}".strip()]
        substring = any(name in c for c in candidates if c)
        ratio = max(
            (SequenceMatcher(None, name, c).ratio() for c in candidates if c),
            default=0.0,
        )
        score = 1.0 if substring else ratio
        if score >= 0.6:
            scored.append((score, row))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [row for _, row in scored]


# --- absence_requests (company_id présent) ---


def absence_summary(company_id: str, filters: dict[str, Any]) -> dict[str, Any]:
    """Synthèse des demandes d'absence de l'entreprise (comptes par statut / type)."""
    company_id = _require_company_id(company_id)
    filters = filters or {}
    query = (
        get_supabase_client()
        .table("absence_requests")
        .select("id, type, status, selected_days")
        .eq("company_id", company_id)
    )
    status = filters.get("status")
    if status:
        query = query.eq("status", str(status))
    atype = filters.get("type")
    if atype:
        query = query.eq("type", str(atype))
    rows = query.execute().data or []

    by_status: dict[str, int] = {}
    by_type: dict[str, int] = {}
    total_selected_days = 0
    for row in rows:
        st = str(row.get("status") or "inconnu")
        ty = str(row.get("type") or "inconnu")
        by_status[st] = by_status.get(st, 0) + 1
        by_type[ty] = by_type.get(ty, 0) + 1
        selected = row.get("selected_days") or []
        if isinstance(selected, list):
            total_selected_days += len(selected)

    return {
        "total_requests": len(rows),
        "by_status": by_status,
        "by_type": by_type,
        "total_selected_days": total_selected_days,
    }


# --- shifts (company_id présent) ---


def planning_summary(company_id: str, filters: dict[str, Any]) -> dict[str, Any]:
    """Synthèse du planning (shifts) de l'entreprise sur une plage de dates."""
    company_id = _require_company_id(company_id)
    filters = filters or {}
    date_start, date_end = _resolve_date_range(filters)

    rows = (
        get_supabase_client()
        .table("shifts")
        .select("id, employee_id, shift_date, is_locked, transverse_category")
        .eq("company_id", company_id)
        .gte("shift_date", date_start)
        .lte("shift_date", date_end)
        .execute()
        .data
        or []
    )

    employees = {
        str(r.get("employee_id")) for r in rows if r.get("employee_id")
    }
    locked = sum(1 for r in rows if r.get("is_locked"))
    return {
        "date_start": date_start,
        "date_end": date_end,
        "total_shifts": len(rows),
        "employees_scheduled": len(employees),
        "locked_shifts": locked,
    }


# --- Agrégats délégués à des services déjà scopés par entreprise ---


def payroll_summary(company_id: str, filters: dict[str, Any]) -> dict[str, Any]:
    """Synthèse paie : délègue à l'analytics paie scopée par entreprise."""
    company_id = _require_company_id(company_id)
    filters = filters or {}
    period = _resolve_period(filters.get("period"))
    return get_payroll_analytics_summary(
        company_id=company_id, period=period, team_ids=None
    )


def hr_indicators(company_id: str, filters: dict[str, Any]) -> dict[str, Any]:
    """Indicateurs RH synthétiques : délègue au dashboard et sérialise un sous-ensemble."""
    company_id = _require_company_id(company_id)
    analytics = build_analytics_avances(company_id)
    return {
        "effectif_actif": analytics.effectif_actif,
        "age_moyen": analytics.age_moyen,
        "anciennete_moyenne_annees": analytics.anciennete_moyenne_annees,
        "masse_salariale_brute_totale": analytics.masse_salariale_brute_totale,
        "turnover": {
            "taux_turnover_annuel": analytics.turnover.taux_turnover_annuel,
            "nb_departs_12_mois": analytics.turnover.nb_departs_12_mois,
            "nb_embauches_12_mois": analytics.turnover.nb_embauches_12_mois,
        },
        "absenteisme": {
            "taux_global": analytics.absenteisme.taux_global,
            "taux_maladie": analytics.absenteisme.taux_maladie,
            "taux_at": analytics.absenteisme.taux_at,
        },
    }
