"""
Mappers : données brutes (DB / domain) -> schémas de réponse dashboard.

Aucune logique métier pure : uniquement conversion de forme.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Any, Dict, List

from app.modules.dashboard.application.dto import ABSENCE_TYPE_LABELS, MONTH_NAMES_FR
from app.modules.dashboard.schemas.responses import (
    ChartDataPoint,
    SimpleEmployee,
    TeamPulseEmployee,
    TeamPulseEvent,
)


def to_team_pulse_employees(
    absences_with_employee: List[dict],
    type_labels: Dict[str, str] | None = None,
) -> List[TeamPulseEmployee]:
    """
    Absences validées du jour (avec employee joint) -> liste TeamPulseEmployee.
    type_labels : mapping type absence -> libellé (défaut ABSENCE_TYPE_LABELS).
    """
    labels = type_labels or ABSENCE_TYPE_LABELS
    result: List[TeamPulseEmployee] = []
    for row in absences_with_employee:
        emp = row.get("employee")
        if not emp:
            continue
        result.append(
            TeamPulseEmployee(
                id=emp["id"],
                first_name=emp.get("first_name", ""),
                last_name=emp.get("last_name", ""),
                status=labels.get(row.get("type") or "", "Absent"),
            )
        )
    return result


def to_team_pulse_events(events_raw: List[Dict[str, Any]]) -> List[TeamPulseEvent]:
    """Liste de dicts (id, type, employee_name, date, detail) -> List[TeamPulseEvent]."""
    out: List[TeamPulseEvent] = []
    for e in events_raw:
        d = e.get("date")
        if isinstance(d, str):
            d = date.fromisoformat(d)
        out.append(
            TeamPulseEvent(
                id=e.get("id", ""),
                type=e.get("type", "birthday"),
                employee_name=e.get("employee_name", ""),
                date=d,
                detail=e.get("detail", ""),
            )
        )
    return out


def aggregate_payslip_costs_and_net(payslips: List[dict]) -> tuple[Dict[int, float], Dict[int, float]]:
    """
    Agrège payslip_data (pied_de_page.cout_total_employeur, net_a_payer) par month.
    Retourne (costs_by_month, net_by_month).
    """
    costs_by_month: Dict[int, float] = defaultdict(float)
    net_by_month: Dict[int, float] = defaultdict(float)
    for row in payslips:
        month = row.get("month")
        payslip_data = row.get("payslip_data")
        if month is None or not payslip_data or not isinstance(payslip_data, dict):
            continue
        pied = payslip_data.get("pied_de_page") or {}
        cout = pied.get("cout_total_employeur", 0) or 0
        net = payslip_data.get("net_a_payer", 0) or 0
        if cout:
            costs_by_month[month] += cout
        if net:
            net_by_month[month] += net
    return dict(costs_by_month), dict(net_by_month)


def to_chart_data_points(
    costs_by_month: Dict[int, float],
    net_by_month: Dict[int, float],
    sorted_months: List[int],
    month_names: Dict[int, str] | None = None,
    empty_label: str = "Aucune donnée",
) -> List[ChartDataPoint]:
    """Construit la liste ChartDataPoint pour le graphique (nom mois, Net_Verse, Charges)."""
    names = month_names or MONTH_NAMES_FR
    out: List[ChartDataPoint] = []
    for month_num in sorted_months:
        cout_total = costs_by_month.get(month_num, 0)
        net_verse = net_by_month.get(month_num, 0)
        charges = cout_total - net_verse
        out.append(
            ChartDataPoint(
                name=names.get(month_num, str(month_num)),
                Net_Verse=round(net_verse, 2),
                Charges=round(charges, 2),
            )
        )
    if not out:
        out = [ChartDataPoint(name=empty_label, Net_Verse=0, Charges=0)]
    return out


def to_simple_employees(employees: List[dict]) -> List[SimpleEmployee]:
    """Liste de dicts employés (id, first_name, last_name) -> List[SimpleEmployee]."""
    return [
        SimpleEmployee(
            id=e["id"],
            first_name=e.get("first_name", ""),
            last_name=e.get("last_name", ""),
        )
        for e in employees
    ]
