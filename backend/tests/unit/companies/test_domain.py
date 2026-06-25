"""
Tests unitaires du domaine companies : entités, value objects, règles pures (KPIs).

Sans DB, sans HTTP. Couvre Company, CompanySettings et compute_company_kpis.
"""

from datetime import date, timedelta

from app.modules.companies.domain.entities import Company
from app.modules.companies.domain.value_objects import CompanySettings
from app.modules.companies.domain.kpis import compute_company_kpis
from app.modules.payroll.domain.payroll_kpi_resolver import PayrollPeriodSnapshot


def _snap(
    period: str,
    *,
    source: str = "payslip",
    gross: float = 0.0,
    net: float = 0.0,
    employer_cost: float = 0.0,
    employee_charges: float = 0.0,
    employer_charges: float = 0.0,
) -> PayrollPeriodSnapshot:
    return PayrollPeriodSnapshot(
        period=period,
        source=source,  # type: ignore[arg-type]
        source_label=f"Test · {period}",
        gross=gross,
        net=net,
        employer_cost=employer_cost,
        employee_charges=employee_charges,
        employer_charges=employer_charges,
    )


def _last_month_key() -> str:
    today = date.today()
    last_month = today.replace(day=1) - timedelta(days=1)
    return f"{last_month.year}-{last_month.month:02d}"


class TestCompanyEntity:
    def test_company_creation_minimal(self):
        c = Company(id="c1", company_name="Ma Société")
        assert c.id == "c1"
        assert c.company_name == "Ma Société"
        assert c.siret is None
        assert c.settings is None
        assert c.is_active is True

    def test_company_creation_full(self):
        settings = {"medical_follow_up_enabled": True}
        c = Company(
            id="c2",
            company_name="SARL Test",
            siret="12345678901234",
            settings=settings,
            is_active=False,
        )
        assert c.siret == "12345678901234"
        assert c.settings == settings
        assert c.is_active is False

    def test_company_equality_by_identity(self):
        c1 = Company(id="same", company_name="A")
        c2 = Company(id="same", company_name="B")
        assert c1.id == c2.id


class TestCompanySettingsValueObject:
    def test_medical_follow_up_enabled_true(self):
        s = CompanySettings(raw={"medical_follow_up_enabled": True})
        assert s.medical_follow_up_enabled is True

    def test_medical_follow_up_enabled_false(self):
        assert CompanySettings(raw={}).medical_follow_up_enabled is False
        assert (
            CompanySettings(raw={"medical_follow_up_enabled": False}).medical_follow_up_enabled
            is False
        )

    def test_medical_follow_up_enabled_truthy_value(self):
        s = CompanySettings(raw={"medical_follow_up_enabled": 1})
        assert s.medical_follow_up_enabled is True


class TestComputeCompanyKpis:
    def test_empty_employees_and_series(self):
        kpis = compute_company_kpis([], [])
        assert kpis["total_employees"] == 0
        assert kpis["last_month_gross_salary"] == 0
        assert kpis["payroll_source"] == "none"
        assert kpis["evolution_12_months"] == []

    def test_total_employees_from_list(self):
        employees = [
            {"id": "e1", "contract_type": "CDI", "job_title": "Dev"},
            {"id": "e2", "contract_type": "CDD", "job_title": "Designer"},
        ]
        kpis = compute_company_kpis(employees, [])
        assert kpis["total_employees"] == 2

    def test_last_month_aggregates_from_series(self):
        key = _last_month_key()
        series = [
            _snap(
                key,
                gross=5000.0,
                net=4000.0,
                employer_charges=800.0,
                employee_charges=300.0,
                employer_cost=5800.0,
            )
        ]
        kpis = compute_company_kpis([{"id": "e1"}, {"id": "e2"}], series)
        assert kpis["last_month_gross_salary"] == 5000.0
        assert kpis["last_month_net_salary"] == 4000.0
        assert kpis["last_month_total_cost"] == 5800.0
        assert kpis["payroll_source"] == "payslip"

    def test_dsn_source_in_kpis(self):
        key = _last_month_key()
        series = [_snap(key, source="dsn", gross=12000.0, net=9000.0)]
        kpis = compute_company_kpis([], series)
        assert kpis["last_month_gross_salary"] == 12000.0
        assert kpis["payroll_source"] == "dsn"

    def test_payroll_tax_rate_when_brut_non_zero(self):
        key = _last_month_key()
        series = [
            _snap(
                key,
                gross=1000.0,
                employer_charges=400.0,
                employee_charges=100.0,
                employer_cost=1400.0,
            )
        ]
        kpis = compute_company_kpis([{"id": "e1"}], series)
        assert kpis["payroll_tax_rate"] == 50.0

    def test_contract_distribution(self):
        employees = [
            {"contract_type": "CDI", "job_title": "Dev"},
            {"contract_type": "CDI", "job_title": "Designer"},
            {"contract_type": "CDD", "job_title": "Stagiaire"},
        ]
        kpis = compute_company_kpis(employees, [])
        assert kpis["contract_distribution"] == {"CDI": 2, "CDD": 1}

    def test_evolution_includes_payroll_source(self):
        key = _last_month_key()
        series = [_snap(key, gross=1000.0, net=800.0, employer_cost=1000.0)]
        kpis = compute_company_kpis([], series)
        assert kpis["evolution_12_months"]
        assert kpis["evolution_12_months"][-1]["payroll_source"] == "payslip"
