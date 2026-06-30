"""Tests unitaires — resolver KPIs paie (bulletins vs DSN)."""

from app.modules.payroll.domain.payroll_kpi_resolver import (
    DsnPeriodTotals,
    PayslipPeriodTotals,
    aggregate_payslips_by_period,
    align_net_with_gross,
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
            employee_charges=3000.0,
            employer_charges=3500.0,
            employee_count=10,
            employees_with_gross=9,
        ),
        dsn_sync_mode="external",
    )
    assert snap.source == "dsn"
    assert snap.gross == 12000.0
    assert snap.net == 9000.0
    assert snap.net <= snap.gross
    assert snap.employee_charges == 3000.0
    assert snap.employer_charges == 3500.0
    assert snap.employer_cost == 15500.0
    assert snap.partial is True


def test_resolve_period_dsn_partial_net_capped_when_exceeds_gross():
    snap = resolve_period_snapshot(
        "2026-02",
        payslip_totals=PayslipPeriodTotals(),
        dsn_totals=DsnPeriodTotals(
            gross=255336.0,
            net_imposable=278361.0,
            employee_count=107,
            employees_with_gross=89,
        ),
        dsn_sync_mode="transition",
    )
    assert snap.source == "dsn"
    assert snap.net <= snap.gross
    assert snap.partial is True


def test_resolve_period_dsn_partial_keeps_employer_charges():
    snap = resolve_period_snapshot(
        "2026-02",
        payslip_totals=PayslipPeriodTotals(),
        dsn_totals=DsnPeriodTotals(
            gross=255336.0,
            net_imposable=247742.0,
            employee_count=100,
            employees_with_gross=89,
            employer_charges=145000.0,
        ),
        dsn_sync_mode="transition",
    )
    assert snap.partial is True
    assert snap.employer_charges == 145000.0
    assert snap.employer_cost == round(255336.0 + 145000.0, 2)


def test_align_net_with_gross_caps_above_gross():
    net = align_net_with_gross(
        1000.0,
        1500.0,
        employee_charges=220.0,
    )
    assert net == 780.0
    assert net <= 1000.0


def test_dsn_row_to_totals_fallback_employee_charges():
    from app.modules.payroll.domain.payroll_kpi_resolver import dsn_row_to_totals

    totals = dsn_row_to_totals(
        {"gross_salary": 24049.34, "net_imposable": 19547.93, "employee_count": 5}
    )
    assert totals.employee_charges == round(24049.34 - 19547.93, 2)


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
