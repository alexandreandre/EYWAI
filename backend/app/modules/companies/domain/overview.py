"""
Règles métier pures : indicateurs RH pour la vue Mon Entreprise (overview).
"""

from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Set

from app.modules.dashboard.domain import rules as dashboard_rules


def _parse_date(value: Any) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    raw = str(value)[:10]
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def _is_cadre(statut: Any) -> bool:
    low = str(statut or "").strip().lower().replace(" ", "").replace("-", "")
    return "cadre" in low and "noncadre" not in low


def _active_employees(employees: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for emp in employees:
        status = str(emp.get("employment_status") or emp.get("status") or "actif").lower()
        if status in ("actif", "active", ""):
            out.append(emp)
    return out if out else list(employees)


def compute_demographics(employees: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Démographie effectif : ETP, ancienneté, âge, cadres, ratio H/F si disponible."""
    active = _active_employees(employees)
    today = date.today()
    total = len(active)
    if total == 0:
        return {
            "total_headcount": 0,
            "total_etp": 0.0,
            "average_tenure_years": 0.0,
            "average_age_years": 0.0,
            "cadre_percent": 0.0,
            "male_percent": None,
            "female_percent": None,
        }

    etp_sum = 0.0
    tenure_years: List[float] = []
    ages: List[float] = []
    cadre_count = 0
    male = 0
    female = 0
    gender_known = 0

    for emp in active:
        wh = emp.get("weekly_hours") or emp.get("duree_hebdomadaire")
        try:
            hours = float(wh) if wh is not None else 35.0
        except (TypeError, ValueError):
            hours = 35.0
        etp_sum += hours / 35.0

        hire = _parse_date(emp.get("hire_date"))
        if hire:
            tenure_years.append((today - hire).days / 365.25)

        bday = _parse_date(
            emp.get("date_naissance") or emp.get("birth_date") or emp.get("birthdate")
        )
        if bday:
            ages.append((today - bday).days / 365.25)

        if _is_cadre(emp.get("statut")):
            cadre_count += 1

        genre = str(emp.get("sexe") or emp.get("gender") or emp.get("genre") or "").strip().lower()
        if genre in ("m", "h", "homme", "male", "masculin"):
            male += 1
            gender_known += 1
        elif genre in ("f", "femme", "female", "féminin", "feminin"):
            female += 1
            gender_known += 1

    male_pct = round(male / gender_known * 100, 1) if gender_known else None
    female_pct = round(female / gender_known * 100, 1) if gender_known else None

    return {
        "total_headcount": total,
        "total_etp": round(etp_sum, 2),
        "average_tenure_years": round(sum(tenure_years) / len(tenure_years), 1)
        if tenure_years
        else 0.0,
        "average_age_years": round(sum(ages) / len(ages), 1) if ages else 0.0,
        "cadre_percent": round(cadre_count / total * 100, 1),
        "male_percent": male_pct,
        "female_percent": female_pct,
    }


def compute_movements(
    employees: List[Dict[str, Any]],
    exits: List[Dict[str, Any]],
    *,
    days_30: int = 30,
    days_90: int = 90,
    days_365: int = 365,
) -> Dict[str, Any]:
    """Entrées / sorties / turn-over sur fenêtres glissantes."""
    today = date.today()
    active = _active_employees(employees)
    headcount = len(active) or 1

    def hires_since(delta_days: int) -> int:
        cutoff = (today - timedelta(days=delta_days)).isoformat()
        return sum(
            1
            for e in employees
            if e.get("hire_date") and str(e.get("hire_date")) >= cutoff
        )

    def exits_since(delta_days: int) -> int:
        cutoff = (today - timedelta(days=delta_days)).isoformat()
        count = 0
        for ex in exits:
            d = ex.get("exit_date") or ex.get("departure_date") or ex.get("created_at")
            if d and str(d)[:10] >= cutoff:
                count += 1
        return count

    hires_12m = hires_since(days_365)
    exits_12m = exits_since(days_365)
    avg_headcount = max(headcount, 1)
    turnover_rate = round(exits_12m / avg_headcount * 100, 1) if exits_12m else 0.0

    return {
        "new_hires_30_days": hires_since(days_30),
        "new_hires_90_days": hires_since(days_90),
        "new_hires_12_months": hires_12m,
        "exits_30_days": exits_since(days_30),
        "exits_90_days": exits_since(days_90),
        "exits_12_months": exits_12m,
        "turnover_rate_12_months": turnover_rate,
    }


def compute_absenteeism(
    absences: List[Dict[str, Any]],
    employee_ids: Set[str],
    *,
    window_days: int = 30,
) -> Dict[str, Any]:
    """Taux d'absentéisme et top motifs sur la fenêtre."""
    today = date.today()
    start = today - timedelta(days=window_days)
    working_days = dashboard_rules.count_working_days_between(start, today)
    theoretical = working_days * len(employee_ids) if employee_ids else 0

    total_days = dashboard_rules.count_absence_days_in_range(
        absences, employee_ids, start, today
    )
    rate = (
        dashboard_rules.compute_absenteeism_rate(total_days, theoretical)
        if theoretical > 0
        else 0.0
    )

    type_counter: Counter[str] = Counter()
    for absence in absences:
        if absence.get("employee_id") not in employee_ids:
            continue
        t = str(absence.get("type") or "Autre")
        type_counter[t] += 1

    top_types = [
        {"type": k, "count": v}
        for k, v in type_counter.most_common(5)
    ]

    return {
        "absenteeism_rate_percent": round(rate, 2),
        "absence_days_last_30": total_days,
        "top_absence_types": top_types,
    }


def compute_alerts(
    company_data: Dict[str, Any],
    employees: List[Dict[str, Any]],
    mutuelle_employee_ids: Set[str],
    *,
    cdd_horizon_days: int = 30,
) -> List[Dict[str, Any]]:
    """Alertes conformité et opérationnelles."""
    alerts: List[Dict[str, Any]] = []
    today = date.today()
    horizon = today + timedelta(days=cdd_horizon_days)
    active = _active_employees(employees)

    if company_data.get("taux_at_mp") is None:
        alerts.append(
            {
                "code": "missing_at_mp",
                "severity": "warning",
                "label": "Taux AT/MP non renseigné",
            }
        )
    if company_data.get("taux_vm") is None:
        alerts.append(
            {
                "code": "missing_vm",
                "severity": "warning",
                "label": "Taux versement mobilité non renseigné",
            }
        )
    if not (company_data.get("collective_agreement") or company_data.get("idcc")):
        alerts.append(
            {
                "code": "missing_collective_agreement",
                "severity": "warning",
                "label": "Convention collective non renseignée",
            }
        )

    headcount = len(active)
    if headcount >= 11:
        alerts.append(
            {
                "code": "cse_threshold",
                "severity": "info",
                "label": f"Effectif {headcount} — vérifier obligations CSE",
            }
        )

    cdd_ending = 0
    for emp in active:
        ctype = str(emp.get("contract_type") or "").upper()
        if "CDD" not in ctype:
            continue
        end = _parse_date(emp.get("contract_end_date"))
        if end and today <= end <= horizon:
            cdd_ending += 1
    if cdd_ending:
        alerts.append(
            {
                "code": "cdd_ending_soon",
                "severity": "warning",
                "label": f"{cdd_ending} CDD se terminent sous {cdd_horizon_days} jours",
                "count": cdd_ending,
            }
        )

    without_mutuelle = 0
    for emp in active:
        if emp.get("id") not in mutuelle_employee_ids:
            without_mutuelle += 1
    if without_mutuelle and mutuelle_employee_ids:
        alerts.append(
            {
                "code": "employees_without_mutuelle",
                "severity": "info",
                "label": f"{without_mutuelle} salarié(s) sans mutuelle affectée",
                "count": without_mutuelle,
            }
        )

    return alerts


def compute_compliance_flags(company_data: Dict[str, Any], headcount: int) -> Dict[str, bool]:
    """Drapeaux pour le bandeau conformité."""
    return {
        "at_mp_configured": company_data.get("taux_at_mp") is not None,
        "vm_configured": company_data.get("taux_vm") is not None,
        "collective_agreement_configured": bool(
            company_data.get("collective_agreement") or company_data.get("idcc")
        ),
        "cse_obligation": headcount >= 11,
    }
