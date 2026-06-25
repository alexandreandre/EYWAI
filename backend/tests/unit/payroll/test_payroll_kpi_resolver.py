"""Tests unitaires — resolver KPIs paie (bulletins vs DSN)."""

from app.modules.payroll.domain.payroll_kpi_resolver import (
    DsnPeriodTotals,
    PayslipPeriodTotals,
    aggregate_payslips_by_period,
    build_period_series,
    extract_payslip_period_totals,
    resolve_period_snapshot,
)


def test_extract_payslip_period_totals_eywai_format():
    data = {
        "salaire_brut": 3200.0,
        "net_a_payer": 2500.0,
        "pied_de_page": {"cout_total_employeur": 4100.0},
        "structure_cotisations": {
            "cotisations": [
                {"montant_salarial": 400.0, "montant_patronal": 500.0},
            ]
        },
    }
    totals = extract_payslip_period_totals(data)
    assert totals.gross == 3200.0
    assert totals.net == 2500.0
    assert totals.employer_cost == 4100.0


def test_resolve_period_prefers_payslip_over_dsn():
    snap = resolve_period_snapshot(
        "2026-01",
        payslip_totals=PayslipPeriodTotals(gross=5000.0, net=3500.0, employer_cost=6500.0),
        dsn_totals=DsnPeriodTotals(gross=4800.0, net_imposable=3400.0),
        dsn_sync_mode="transition",
    )
    assert snap.source == "payslip"
    assert snap.gross == 5000.0


def test_resolve_period_dsn_when_no_payslip_and_transition():
    snap = resolve_period_snapshot(
        "2026-02",
        payslip_totals=PayslipPeriodTotals(),
        dsn_totals=DsnPeriodTotals(
            gross=12000.0,
            net_imposable=9000.0,
            employee_count=10,
            employees_with_gross=9,
        ),
        dsn_sync_mode="external",
    )
    assert snap.source == "dsn"
    assert snap.gross == 12000.0
    assert snap.partial is True


def test_resolve_period_native_no_dsn_fallback():
    snap = resolve_period_snapshot(
        "2026-02",
        payslip_totals=PayslipPeriodTotals(),
        dsn_totals=DsnPeriodTotals(gross=12000.0),
        dsn_sync_mode="native",
    )
    assert snap.source == "none"
    assert snap.gross == 0.0


def test_aggregate_payslips_by_period():
    rows = aggregate_payslips_by_period(
        [
            {"year": 2026, "month": 1, "payslip_data": {"salaire_brut": 1000.0}},
            {"year": 2026, "month": 1, "payslip_data": {"salaire_brut": 500.0}},
        ]
    )
    assert rows["2026-01"].gross == 1500.0


def test_build_period_series_mixed_sources():
    series = build_period_series(
        ["2026-01", "2026-02"],
        {"2026-01": PayslipPeriodTotals(gross=1000.0)},
        {"2026-02": DsnPeriodTotals(gross=2000.0, employee_count=2, employees_with_gross=2)},
        "transition",
    )
    assert series[0].source == "payslip"
    assert series[1].source == "dsn"
