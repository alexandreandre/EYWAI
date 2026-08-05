"""Tests unitaires — rapport d'anomalies paie (filtrage)."""

from unittest.mock import MagicMock, patch

from app.modules.payslips.application.anomalies_report import (
    _collect_anomalies_for_row,
    _dedupe_system_config_anomalies,
)
from app.modules.payslips.domain.anomaly_visibility import EmployeeAnomalyContext
from app.modules.payslips.schemas.anomalies import AnomaliePayslipItem


def _row(
    *,
    brut: float = 2000.0,
    status: str = "valide",
    alertes_baremes=None,
):
    return {
        "id": "ps-1",
        "employee_id": "emp-1",
        "status": status,
        "created_at": "2026-06-01T10:00:00+00:00",
        "updated_at": "2026-06-01T10:00:00+00:00",
        "employees": {"first_name": "Fredo", "last_name": "André", "employment_status": "actif"},
        "payslip_data": {
            "salaire_brut": brut,
            "net_a_payer": brut * 0.75,
            "calcul_du_brut": [],
            "structure_cotisations": {"cotisations": []},
            "alertes_baremes": alertes_baremes or [],
        },
    }


class TestCollectAnomaliesFiltering:
    def test_hides_motor_warnings_when_settled(self):
        alertes = [
            {
                "code": "bareme_chemin_invalide",
                "critique": False,
                "message": "Chemin invalide heures_supp.x",
            }
        ]
        row = _row(alertes_baremes=alertes)
        ctx = EmployeeAnomalyContext(employment_status="actif")
        out = _collect_anomalies_for_row(
            row,
            year=2026,
            month=6,
            period_closed=True,
            employee_ctx=ctx,
        )
        assert out == []

    def test_keeps_blocking_brut_negatif_on_open_period(self):
        row = _row(brut=-10.22, status="brouillon")
        ctx = EmployeeAnomalyContext(employment_status="actif")
        out = _collect_anomalies_for_row(
            row,
            year=2026,
            month=6,
            period_closed=False,
            employee_ctx=ctx,
        )
        types = {item.type for item in out}
        assert "BRUT_NEGATIF" in types


class TestDedupeSystemConfigAnomalies:
    def test_keeps_one_row_per_config_message(self):
        items = [
            AnomaliePayslipItem(
                employee_id="e1",
                employee_name="A",
                payslip_id="p1",
                type="ALERTE_BAREME_CHEMIN_INVALIDE",
                severite="avertissement",
                message="Chemin invalide heures_supp.x",
                valeur_detectee="moteur_paie",
                suggestion_correction="",
            ),
            AnomaliePayslipItem(
                employee_id="e2",
                employee_name="B",
                payslip_id="p2",
                type="ALERTE_BAREME_CHEMIN_INVALIDE",
                severite="avertissement",
                message="Chemin invalide heures_supp.x",
                valeur_detectee="moteur_paie",
                suggestion_correction="",
            ),
        ]
        out = _dedupe_system_config_anomalies(items)
        assert len(out) == 1


class TestBuildReportIntegration:
    @patch("app.modules.payslips.application.anomalies_report.supabase")
    @patch(
        "app.modules.payslips.application.anomalies_report.payroll_analytics_repository"
    )
    def test_excludes_post_exit_payslip(self, mock_repo, mock_supabase):
        from app.modules.payslips.application.anomalies_report import (
            build_payslips_anomalies_report,
        )

        mock_repo.is_period_closed.return_value = False

        exits_chain = MagicMock()
        exits_chain.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[
                {
                    "employee_id": "emp-left",
                    "status": "archivee",
                    "last_working_day": "2026-06-15",
                }
            ]
        )

        payslips_chain = MagicMock()
        payslips_chain.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[
                {
                    "id": "ps-future",
                    "employee_id": "emp-left",
                    "status": "brouillon",
                    "created_at": "2026-07-01T10:00:00+00:00",
                    "updated_at": "2026-07-01T10:00:00+00:00",
                    "employees": {
                        "first_name": "Vitor",
                        "last_name": "Cardoso",
                        "employment_status": "parti",
                    },
                    "payslip_data": {
                        "salaire_brut": -10.22,
                        "net_a_payer": -8.0,
                        "calcul_du_brut": [],
                        "structure_cotisations": {"cotisations": []},
                    },
                }
            ]
        )

        def table_router(name):
            if name == "employee_exits":
                return exits_chain
            if name == "payslips":
                return payslips_chain
            return MagicMock()

        mock_supabase.table.side_effect = table_router

        report = build_payslips_anomalies_report("co-1", 2026, 7)
        assert report.total_bulletins == 0
        assert report.anomalies == []


class TestDelaiValidation:
    """« Non validé » n'est signalé que si la société valide réellement ses bulletins."""

    def _old_row(self):
        row = _row(status="brouillon")
        row["created_at"] = "2026-01-01T10:00:00+00:00"
        row["updated_at"] = "2026-01-01T10:00:00+00:00"
        return row

    def test_silent_when_no_payslip_is_ever_validated(self):
        out = _collect_anomalies_for_row(
            self._old_row(),
            year=2026,
            month=6,
            period_closed=False,
            employee_ctx=EmployeeAnomalyContext(employment_status="actif"),
            validation_workflow_active=False,
        )
        assert "DELAI_VALIDATION" not in {item.type for item in out}

    def test_reported_when_workflow_is_used(self):
        out = _collect_anomalies_for_row(
            self._old_row(),
            year=2026,
            month=6,
            period_closed=False,
            employee_ctx=EmployeeAnomalyContext(employment_status="actif"),
            validation_workflow_active=True,
        )
        assert "DELAI_VALIDATION" in {item.type for item in out}
