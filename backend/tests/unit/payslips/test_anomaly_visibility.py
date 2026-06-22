"""Tests unitaires — visibilité et purge des anomalies paie."""

from datetime import date


from app.modules.payslips.domain.anomaly_visibility import (
    EmployeeAnomalyContext,
    is_period_after_last_working_day,
    is_system_config_anomaly,
    should_include_anomaly_in_report,
    should_include_payslip_in_anomalies_report,
)
from app.modules.payslips.infrastructure.anomaly_cleanup import (
    strip_engine_alerts_from_payslip_data,
)


class TestEmployeeAnomalyContext:
    def test_definitively_left_when_exit_archived(self):
        ctx = EmployeeAnomalyContext(
            employment_status="actif",
            exit_status="archivee",
            last_working_day=date(2026, 5, 15),
        )
        assert ctx.is_definitively_left is True

    def test_definitively_left_when_employment_parti(self):
        ctx = EmployeeAnomalyContext(employment_status="parti")
        assert ctx.is_definitively_left is True


class TestPayslipInclusion:
    def test_excludes_payslip_after_last_working_day(self):
        ctx = EmployeeAnomalyContext(
            employment_status="parti",
            exit_status="archivee",
            last_working_day=date(2026, 5, 15),
        )
        assert should_include_payslip_in_anomalies_report(ctx, year=2026, month=5) is True
        assert should_include_payslip_in_anomalies_report(ctx, year=2026, month=6) is False

    def test_keeps_active_employee_payslip(self):
        ctx = EmployeeAnomalyContext(employment_status="actif")
        assert should_include_payslip_in_anomalies_report(ctx, year=2026, month=6) is True


class TestAnomalyInclusion:
    def test_hides_warnings_when_validated(self):
        ctx = EmployeeAnomalyContext(employment_status="actif")
        assert (
            should_include_anomaly_in_report(
                anomaly_type="ALERTE_BAREME_CHEMIN_INVALIDE",
                severite="avertissement",
                payslip_status="valide",
                period_closed=False,
                employee_ctx=ctx,
            )
            is False
        )

    def test_keeps_blocking_when_open_period(self):
        ctx = EmployeeAnomalyContext(employment_status="actif")
        assert (
            should_include_anomaly_in_report(
                anomaly_type="BRUT_NEGATIF",
                severite="bloquant",
                payslip_status="brouillon",
                period_closed=False,
                employee_ctx=ctx,
            )
            is True
        )

    def test_hides_all_when_left_and_period_closed(self):
        ctx = EmployeeAnomalyContext(
            employment_status="parti",
            exit_status="archivee",
            last_working_day=date(2026, 5, 31),
        )
        assert (
            should_include_anomaly_in_report(
                anomaly_type="BRUT_NEGATIF",
                severite="bloquant",
                payslip_status="brouillon",
                period_closed=True,
                employee_ctx=ctx,
            )
            is False
        )


class TestHelpers:
    def test_is_period_after_last_working_day(self):
        lwd = date(2026, 5, 31)
        assert is_period_after_last_working_day(lwd, 2026, 5) is False
        assert is_period_after_last_working_day(lwd, 2026, 6) is True

    def test_is_system_config_anomaly(self):
        assert is_system_config_anomaly("ALERTE_BAREME_CHEMIN_INVALIDE", "moteur_paie")
        assert not is_system_config_anomaly("BRUT_NEGATIF", "-10.22 €")


class TestStripEngineAlerts:
    def test_removes_alertes_baremes_and_maintien(self):
        pdata = {
            "salaire_brut": 2000,
            "alertes_baremes": [{"code": "bareme_chemin_invalide", "message": "x"}],
            "synthese_net": {"alertes_maintien": ["alerte"]},
        }
        cleaned = strip_engine_alerts_from_payslip_data(pdata)
        assert "alertes_baremes" not in cleaned
        assert "alertes_maintien" not in cleaned["synthese_net"]
        assert pdata["alertes_baremes"]  # original intact
