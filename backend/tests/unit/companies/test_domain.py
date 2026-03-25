"""
Tests unitaires du domaine companies : entités, value objects, règles pures (KPIs).

Sans DB, sans HTTP. Couvre Company, CompanySettings et compute_company_kpis.
"""

from datetime import date, timedelta


from app.modules.companies.domain.entities import Company
from app.modules.companies.domain.value_objects import CompanySettings
from app.modules.companies.domain.kpis import compute_company_kpis


# --- Entité Company ---


class TestCompanyEntity:
    """Entité Company : agrégat entreprise."""

    def test_company_creation_minimal(self):
        """Création avec id et company_name obligatoires."""
        c = Company(id="c1", company_name="Ma Société")
        assert c.id == "c1"
        assert c.company_name == "Ma Société"
        assert c.siret is None
        assert c.settings is None
        assert c.is_active is True

    def test_company_creation_full(self):
        """Création avec tous les champs."""
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
        """Deux Company avec le même id ont la même identité (agrégat)."""
        c1 = Company(id="same", company_name="A")
        c2 = Company(id="same", company_name="B")
        assert c1.id == c2.id


# --- Value object CompanySettings ---


class TestCompanySettingsValueObject:
    """Value object CompanySettings (settings entreprise)."""

    def test_medical_follow_up_enabled_true(self):
        """medical_follow_up_enabled True quand raw.medical_follow_up_enabled est True."""
        s = CompanySettings(raw={"medical_follow_up_enabled": True})
        assert s.medical_follow_up_enabled is True

    def test_medical_follow_up_enabled_false(self):
        """medical_follow_up_enabled False quand clé absente ou False."""
        assert CompanySettings(raw={}).medical_follow_up_enabled is False
        assert (
            CompanySettings(
                raw={"medical_follow_up_enabled": False}
            ).medical_follow_up_enabled
            is False
        )

    def test_medical_follow_up_enabled_truthy_value(self):
        """Valeur truthy (ex. 1) est considérée comme True."""
        s = CompanySettings(raw={"medical_follow_up_enabled": 1})
        assert s.medical_follow_up_enabled is True


# --- Règles KPIs (domain/kpis.py) ---


class TestComputeCompanyKpis:
    """compute_company_kpis : règle pure sans I/O."""

    def test_empty_employees_and_payslips(self):
        """Sans employés ni bulletins : total_employees=0, last_month_* à 0."""
        kpis = compute_company_kpis([], [])
        assert kpis["total_employees"] == 0
        assert kpis["last_month_gross_salary"] == 0
        assert kpis["last_month_net_salary"] == 0
        assert kpis["last_month_employer_charges"] == 0
        assert kpis["last_month_employee_charges"] == 0
        assert kpis["last_month_total_cost"] == 0
        assert kpis["last_month_total_charges"] == 0
        assert kpis["payroll_tax_rate"] == 0
        assert kpis["average_cost_per_employee"] == 0
        assert kpis["evolution_12_months"] == []
        assert kpis["contract_distribution"] == {}
        assert kpis["job_distribution"] == {}
        assert kpis["new_hires_last_30_days"] == 0
        assert "annual_gross_salary" in kpis
        assert "annual_total_cost" in kpis

    def test_total_employees_from_list(self):
        """total_employees = len(all_employees)."""
        employees = [
            {"id": "e1", "contract_type": "CDI", "job_title": "Dev"},
            {"id": "e2", "contract_type": "CDD", "job_title": "Designer"},
        ]
        kpis = compute_company_kpis(employees, [])
        assert kpis["total_employees"] == 2

    def test_last_month_aggregates_from_payslips(self):
        """last_month_* agrégés à partir des bulletins du mois dernier."""
        today = date.today()
        last_month = today.replace(day=1) - timedelta(days=1)
        ym = last_month.year
        mm = last_month.month
        payslips = [
            {
                "month": mm,
                "year": ym,
                "payslip_data": {
                    "remuneration": {"brut": 3000},
                    "net_a_payer": 2400,
                    "cotisations": [
                        {"part_patronale": 500, "part_salariale": 200},
                    ],
                    "pied_de_page": {"cout_total_employeur": 3500},
                },
            },
            {
                "month": mm,
                "year": ym,
                "payslip_data": {
                    "remuneration": {"brut": 2000},
                    "net_a_payer": 1600,
                    "cotisations": [
                        {"part_patronale": 300, "part_salariale": 100},
                    ],
                    "pied_de_page": {"cout_total_employeur": 2300},
                },
            },
        ]
        kpis = compute_company_kpis([{"id": "e1"}, {"id": "e2"}], payslips)
        assert kpis["last_month_gross_salary"] == 5000.0
        assert kpis["last_month_net_salary"] == 4000.0
        assert kpis["last_month_employer_charges"] == 800.0
        assert kpis["last_month_employee_charges"] == 300.0
        assert kpis["last_month_total_cost"] == 5800.0
        assert kpis["last_month_total_charges"] == 1100.0
        assert kpis["last_month_gross_salary"] == 5000.0

    def test_payroll_tax_rate_when_brut_non_zero(self):
        """payroll_tax_rate = (charges patronales + salariales) / brut * 100."""
        today = date.today()
        last_month = today.replace(day=1) - timedelta(days=1)
        payslips = [
            {
                "month": last_month.month,
                "year": last_month.year,
                "payslip_data": {
                    "remuneration": {"brut": 1000},
                    "net_a_payer": 800,
                    "cotisations": [
                        {"part_patronale": 400, "part_salariale": 100},
                    ],
                    "pied_de_page": {"cout_total_employeur": 1400},
                },
            },
        ]
        kpis = compute_company_kpis([{"id": "e1"}], payslips)
        # (400+100)/1000 * 100 = 50
        assert kpis["payroll_tax_rate"] == 50.0

    def test_contract_distribution(self):
        """contract_distribution compte par contract_type."""
        employees = [
            {"contract_type": "CDI", "job_title": "Dev"},
            {"contract_type": "CDI", "job_title": "Designer"},
            {"contract_type": "CDD", "job_title": "Stagiaire"},
        ]
        kpis = compute_company_kpis(employees, [])
        assert kpis["contract_distribution"] == {"CDI": 2, "CDD": 1}

    def test_job_distribution(self):
        """job_distribution compte par job_title."""
        employees = [
            {"contract_type": "CDI", "job_title": "Dev"},
            {"contract_type": "CDI", "job_title": "Dev"},
            {"contract_type": "CDD", "job_title": "Designer"},
        ]
        kpis = compute_company_kpis(employees, [])
        assert kpis["job_distribution"] == {"Dev": 2, "Designer": 1}

    def test_undefined_contract_or_job_mapped_to_non_defini(self):
        """contract_type ou job_title absents → clé 'Non défini' dans les distributions."""
        employees = [{"id": "e1"}]  # pas de contract_type ni job_title
        kpis = compute_company_kpis(employees, [])
        assert kpis["contract_distribution"].get("Non défini", 0) == 1
        assert kpis["job_distribution"].get("Non défini", 0) == 1

    def test_new_hires_last_30_days(self):
        """new_hires_last_30_days = employés avec hire_date dans les 30 derniers jours."""
        today = date.today()
        recent = (today - timedelta(days=10)).isoformat()
        old = (today - timedelta(days=40)).isoformat()
        employees = [
            {"id": "e1", "hire_date": recent},
            {"id": "e2", "hire_date": old},
            {"id": "e3", "hire_date": recent},
        ]
        kpis = compute_company_kpis(employees, [])
        assert kpis["new_hires_last_30_days"] == 2

    def test_evolution_12_months_structure(self):
        """evolution_12_months contient les 12 derniers mois (hors mois courant)."""
        today = date.today()
        last_month = today.replace(day=1) - timedelta(days=1)
        payslips = [
            {
                "month": last_month.month,
                "year": last_month.year,
                "payslip_data": {
                    "remuneration": {"brut": 1000},
                    "net_a_payer": 800,
                    "cotisations": [],
                    "pied_de_page": {"cout_total_employeur": 1000},
                },
            },
        ]
        kpis = compute_company_kpis([], payslips)
        assert "evolution_12_months" in kpis
        assert isinstance(kpis["evolution_12_months"], list)
        # Au moins le dernier mois avec données peut être présent
        for item in kpis["evolution_12_months"]:
            assert "month" in item
            assert "masse_salariale_brute" in item
            assert "net_verse" in item
            assert "charges_totales" in item
            assert "cout_total_employeur" in item

    def test_payslip_without_month_year_ignored(self):
        """Bulletins sans month/year valides ne sont pas agrégés."""
        payslips = [
            {
                "month": None,
                "year": 2024,
                "payslip_data": {"remuneration": {"brut": 9999}},
            },
            {
                "month": 1,
                "year": None,
                "payslip_data": {"remuneration": {"brut": 9999}},
            },
        ]
        kpis = compute_company_kpis([], payslips)
        assert kpis["last_month_gross_salary"] == 0
