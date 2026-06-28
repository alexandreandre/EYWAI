"""Tests unitaires — purge batch des alertes moteur paie."""

from datetime import date
from unittest.mock import MagicMock, patch

from app.modules.payslips.infrastructure.anomaly_cleanup import (
    cleanup_payslips_on_exit_archived,
    purge_all_engine_alerts_from_payslips,
)


class TestPurgeAllEngineAlerts:
    def test_updates_rows_with_alertes_baremes(self):
        sb = MagicMock()
        chain = MagicMock()
        sb.table.return_value = chain
        chain.select.return_value = chain
        chain.range.return_value = chain
        chain.eq.return_value = chain
        chain.update.return_value = chain

        execute_results = [
            MagicMock(
                data=[
                    {
                        "id": "ps-1",
                        "payslip_data": {
                            "salaire_brut": 2000,
                            "alertes_baremes": [{"code": "x", "message": "y"}],
                        },
                    }
                ]
            ),
            MagicMock(data=[]),
        ]
        chain.execute.side_effect = execute_results

        count = purge_all_engine_alerts_from_payslips(sb, page_size=100)
        assert count == 1
        chain.update.assert_called_once()


class TestCleanupExitArchivedRegularisation:
    def _sb_with_rows(self, rows):
        sb = MagicMock()
        chain = MagicMock()
        sb.table.return_value = chain
        chain.select.return_value = chain
        chain.eq.return_value = chain
        chain.execute.return_value = MagicMock(data=rows)
        return sb

    def test_regularisation_bulletin_is_never_deleted(self):
        """Un bulletin de régularisation postérieur au départ ne doit pas être supprimé."""
        rows = [
            {
                "id": "ps-regul",
                "year": 2027,
                "month": 5,
                "status": "valide",
                "payslip_data": {},
                "bulletin_kind": "regularisation_participation",
            },
            {
                "id": "ps-draft",
                "year": 2027,
                "month": 5,
                "status": "brouillon",
                "payslip_data": {},
                "bulletin_kind": None,
            },
        ]
        sb = self._sb_with_rows(rows)
        deleted = []
        with patch(
            "app.modules.payslips.infrastructure.anomaly_cleanup.payslip_repository"
        ) as repo:
            repo.delete.side_effect = lambda pid: deleted.append(pid)
            cleanup_payslips_on_exit_archived(
                "e-1", "c-1", date(2026, 12, 31), supabase_client=sb
            )
        # Seul le brouillon standard postérieur au départ est supprimé.
        assert deleted == ["ps-draft"]
