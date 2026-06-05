"""
Historique des salaires pour l'attestation employeur France Travail.

Règle officielle : 25 derniers mois (37 si le salarié a 55 ans ou plus à la date de fin).
"""

from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

from app.shared.infrastructure.pdf.helpers import safe_float

_MONTH_NAMES = [
    "",
    "Janvier",
    "Février",
    "Mars",
    "Avril",
    "Mai",
    "Juin",
    "Juillet",
    "Août",
    "Septembre",
    "Octobre",
    "Novembre",
    "Décembre",
]


def _parse_date(value: Any) -> Optional[date]:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None


def compute_attestation_month_count(
    birth_date: Any,
    end_date: Any,
) -> int:
    """Retourne 37 si le salarié a 55 ans ou plus à la fin de contrat, sinon 25."""
    bd = _parse_date(birth_date)
    ed = _parse_date(end_date)
    if not bd or not ed:
        return 25
    age = ed.year - bd.year - ((ed.month, ed.day) < (bd.month, bd.day))
    return 37 if age >= 55 else 25


def _iter_months(end_date: date, count: int) -> List[Tuple[int, int]]:
    year = end_date.year
    month = end_date.month
    pairs: List[Tuple[int, int]] = []
    for _ in range(count):
        pairs.append((year, month))
        month -= 1
        if month <= 0:
            month = 12
            year -= 1
    pairs.reverse()
    return pairs


def _month_label(year: int, month: int) -> str:
    name = _MONTH_NAMES[month] if 1 <= month <= 12 else str(month)
    return f"{name} {year}"


def _default_weekly_hours(employee_data: Dict[str, Any]) -> float:
    for key in ("duree_hebdomadaire", "weekly_hours"):
        val = employee_data.get(key)
        if val is not None:
            try:
                return float(val)
            except (TypeError, ValueError):
                pass
    return 35.0


def _fallback_base_salary(employee_data: Dict[str, Any]) -> float:
    sb = employee_data.get("salaire_de_base")
    if isinstance(sb, dict):
        return safe_float(sb.get("valeur", sb.get("amount")), 0.0)
    return safe_float(sb, 0.0)


def _extract_working_time(
    payslip_data: Dict[str, Any],
    employee_data: Dict[str, Any],
) -> str:
    jours = payslip_data.get("nombre_jours_travailles")
    if jours is not None and safe_float(jours) > 0:
        n = safe_float(jours)
        label = "jour" if n == 1 else "jours"
        return f"{n:.2f} {label}"

    heures = payslip_data.get("heures_travaillees")
    if heures is not None and safe_float(heures) > 0:
        n = safe_float(heures)
        return f"{n:.2f} h"

    calcul = payslip_data.get("calcul_du_brut") or []
    heures_calc = 0.0
    for line in calcul:
        if not isinstance(line, dict):
            continue
        libelle = str(line.get("libelle", "")).lower()
        if "heure" in libelle and line.get("quantite"):
            heures_calc += safe_float(line.get("quantite"))
    if heures_calc > 0:
        return f"{heures_calc:.2f} h"

    weekly = _default_weekly_hours(employee_data)
    monthly_hours = round((weekly * 52) / 12, 2)
    return f"{monthly_hours:.2f} h"


def _extract_absences(payslip_data: Dict[str, Any]) -> str:
    details = payslip_data.get("details_absences") or []
    total_jours = 0.0
    total_heures = 0.0
    for line in details:
        if not isinstance(line, dict):
            continue
        qty = line.get("quantite") or line.get("jours") or line.get("nombre_jours")
        if qty is not None:
            unit = str(line.get("unite", "")).lower()
            if unit.startswith("h"):
                total_heures += safe_float(qty)
            else:
                total_jours += safe_float(qty)
    if total_heures > 0:
        return f"{total_heures:.2f} h"
    if total_jours > 0:
        label = "jour" if total_jours == 1 else "jours"
        return f"{total_jours:.2f} {label}"
    return "Néant"


def _extract_primes(payslip_data: Dict[str, Any]) -> float:
    direct = safe_float(payslip_data.get("total_primes"), 0.0)
    if direct > 0:
        return direct
    total = 0.0
    for line in payslip_data.get("calcul_du_brut") or []:
        if not isinstance(line, dict):
            continue
        libelle = str(line.get("libelle", "")).lower()
        if "prime" in libelle:
            total += safe_float(line.get("gain"), 0.0)
    return total


def _fetch_payslip_map(
    employee_id: str,
    supabase_client: Any,
) -> Dict[Tuple[int, int], Dict[str, Any]]:
    if not employee_id or not supabase_client:
        return {}
    try:
        resp = (
            supabase_client.table("payslips")
            .select("year, month, payslip_data")
            .eq("employee_id", employee_id)
            .execute()
        )
        rows = resp.data if resp and hasattr(resp, "data") else []
        return {
            (int(row["year"]), int(row["month"])): row
            for row in (rows or [])
            if row.get("year") is not None and row.get("month") is not None
        }
    except Exception:
        return {}


def _normalize_custom_row(row: Dict[str, Any], year: int, month: int) -> Dict[str, Any]:
    return {
        "year": int(row.get("year", year)),
        "month": int(row.get("month", month)),
        "period_label": row.get("period_label") or _month_label(year, month),
        "working_time": str(row.get("working_time") or row.get("temps_travail") or "Néant"),
        "absences": str(row.get("absences") or "Néant"),
        "gross_salary": safe_float(
            row.get("gross_salary") or row.get("salaire_brut"), 0.0
        ),
        "primes": safe_float(row.get("primes") or row.get("total_primes"), 0.0),
        "has_payslip": bool(row.get("has_payslip", True)),
        "is_estimated": bool(row.get("is_estimated", False)),
    }


def get_salary_history(
    employee_id: str,
    employee_data: Dict[str, Any],
    end_date: Any,
    supabase_client: Any = None,
    month_count: Optional[int] = None,
    custom_rows: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Construit l'historique des salaires pour l'attestation employeur.

    Retourne month_count, months (liste de lignes), total_brut, primes_lines.
    """
    ed = _parse_date(end_date) or date.today()
    count = month_count or compute_attestation_month_count(
        employee_data.get("date_naissance") or employee_data.get("birthdate"),
        ed,
    )

    if custom_rows:
        months = [
            _normalize_custom_row(
                row,
                int(row.get("year", ed.year)),
                int(row.get("month", ed.month)),
            )
            for row in custom_rows
        ]
    else:
        payslip_map = _fetch_payslip_map(employee_id, supabase_client)
        fallback_salary = _fallback_base_salary(employee_data)
        months = []
        for year, month in _iter_months(ed, count):
            row_data = payslip_map.get((year, month))
            if row_data:
                pdata = row_data.get("payslip_data") or {}
                brut = safe_float(pdata.get("salaire_brut"), 0.0)
                if brut <= 0:
                    brut = fallback_salary
                months.append(
                    {
                        "year": year,
                        "month": month,
                        "period_label": _month_label(year, month),
                        "working_time": _extract_working_time(pdata, employee_data),
                        "absences": _extract_absences(pdata),
                        "gross_salary": brut,
                        "primes": _extract_primes(pdata),
                        "has_payslip": True,
                        "is_estimated": brut <= 0,
                    }
                )
            else:
                months.append(
                    {
                        "year": year,
                        "month": month,
                        "period_label": _month_label(year, month),
                        "working_time": f"{round((_default_weekly_hours(employee_data) * 52) / 12, 2):.2f} h",
                        "absences": "Néant",
                        "gross_salary": fallback_salary,
                        "primes": 0.0,
                        "has_payslip": False,
                        "is_estimated": True,
                    }
                )

        if ed.day < monthrange(ed.year, ed.month)[1]:
            last = months[-1] if months else None
            if last and last["year"] == ed.year and last["month"] == ed.month:
                last["period_label"] = (
                    f"{_month_label(ed.year, ed.month)} "
                    f"(du 01/{ed.month:02d}/{ed.year} au {ed.day:02d}/{ed.month:02d}/{ed.year})"
                )

    total_brut = sum(safe_float(m.get("gross_salary"), 0.0) for m in months)
    primes_lines: List[Dict[str, Any]] = []
    for m in months:
        primes = safe_float(m.get("primes"), 0.0)
        if primes > 0:
            primes_lines.append(
                {
                    "nature": f"Primes — {m.get('period_label', '')}",
                    "montant": primes,
                }
            )

    period_start = date(months[0]["year"], months[0]["month"], 1) if months else ed
    last_m = months[-1] if months else {"year": ed.year, "month": ed.month}
    last_day = monthrange(last_m["year"], last_m["month"])[1]
    period_end = date(last_m["year"], last_m["month"], last_day)

    return {
        "month_count": count,
        "months": months,
        "total_brut": round(total_brut, 2),
        "primes_lines": primes_lines,
        "period_start": period_start,
        "period_end": period_end,
    }
