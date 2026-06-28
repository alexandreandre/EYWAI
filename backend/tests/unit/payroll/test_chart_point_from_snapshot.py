"""Tests unitaires — points graphique coûts dashboard."""

from app.modules.payroll.application.payroll_kpi_queries import chart_point_from_snapshot
from app.modules.payroll.domain.payroll_kpi_resolver import PayrollPeriodSnapshot


def test_chart_point_dsn_gross_stack():
    snap = PayrollPeriodSnapshot(
        period="2026-05",
        source="dsn",
        source_label="Masse déclarée (DSN)",
        gross=24049.34,
        net=19547.93,
        employer_cost=0.0,
        employee_charges=4501.41,
        employer_charges=0.0,
    )
    point = chart_point_from_snapshot(snap)
    assert point["stackMode"] == "gross"
    assert point["Net_Verse"] == 19547.93
    assert point["Charges"] == 4501.41
    assert round(point["Net_Verse"] + point["Charges"], 2) == 24049.34


def test_chart_point_dsn_employer_cost_stack():
    snap = PayrollPeriodSnapshot(
        period="2026-05",
        source="dsn",
        source_label="Masse déclarée (DSN)",
        gross=24049.34,
        net=19547.93,
        employer_cost=31000.0,
        employee_charges=4501.41,
        employer_charges=6950.66,
    )
    point = chart_point_from_snapshot(snap)
    assert point["stackMode"] == "employer_cost"
    assert point["Charges"] == round(31000.0 - 19547.93, 2)


def test_chart_point_payslip_employer_cost_stack():
    snap = PayrollPeriodSnapshot(
        period="2026-05",
        source="payslip",
        source_label="Bulletins validés",
        gross=3200.0,
        net=2500.0,
        employer_cost=4100.0,
        employee_charges=400.0,
        employer_charges=500.0,
    )
    point = chart_point_from_snapshot(snap)
    assert point["stackMode"] == "employer_cost"
    assert point["Charges"] == 1600.0
