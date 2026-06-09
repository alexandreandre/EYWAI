"""Tests unitaires — purge batch des alertes moteur paie."""

from unittest.mock import MagicMock

from app.modules.payslips.infrastructure.anomaly_cleanup import (
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
