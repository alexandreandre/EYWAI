"""
Tests unitaires du service dispatch (envois compta / banque).
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.modules.exports.application import dispatch as dispatch_service
from app.modules.exports.schemas import ExportGenerateResponse, ExportPreviewResponse, ExportTotals
from app.modules.exports.schemas.dispatch import DispatchBanqueRequest, DispatchComptaRequest

pytestmark = pytest.mark.unit


def _preview(can_generate: bool = True, blocking: int = 0) -> ExportPreviewResponse:
    anomalies = []
    if blocking:
        from app.modules.exports.schemas import ExportAnomaly

        anomalies = [
            ExportAnomaly(
                type="error",
                message="IBAN manquant",
                severity="blocking",
            )
        ] * blocking
    return ExportPreviewResponse(
        export_type="od_globale",
        period="2025-05",
        employees_count=3,
        totals=ExportTotals(employees_count=3, total_brut=12000.0, total_net_a_payer=9000.0),
        anomalies=anomalies,
        warnings=[],
        can_generate=can_generate and blocking == 0,
    )


def _generate_response(export_id: str, export_type: str = "od_globale") -> ExportGenerateResponse:
    from app.modules.exports.schemas import ExportFileInfo, ExportReport

    now = datetime.now(timezone.utc)
    return ExportGenerateResponse(
        export_id=export_id,
        export_type=export_type,
        period="2025-05",
        status="generated",
        files=[ExportFileInfo(filename="f.csv", path="p/f.csv", size=100, format="csv")],
        report=ExportReport(
            export_type=export_type,
            period="2025-05",
            generated_at=now,
            generated_by="user-1",
            employees_count=3,
            totals=ExportTotals(employees_count=3),
        ),
        download_urls={"f.csv": "https://example.com/f.csv"},
    )


class TestGetDispatchStatus:
    def test_pending_when_no_row(self):
        with patch.object(dispatch_service, "_get_dispatch_row", return_value=None), patch.object(
            dispatch_service, "_preview_channel", return_value={"can_generate": True, "blocking_anomalies_count": 0, "totals": ExportTotals(employees_count=2)}
        ):
            result = dispatch_service.get_dispatch_status("co-1", "2025-05")
            assert result.compta.status == "pending"
            assert result.banque.status == "pending"

    def test_generated_when_row_exists(self):
        row = {
            "id": "disp-1",
            "status": "generated",
            "export_ids": ["exp-1", "exp-2"],
            "created_at": "2025-06-01T10:00:00+00:00",
            "transmitted_at": None,
            "transmission_note": None,
        }
        with patch.object(dispatch_service, "_get_dispatch_row", return_value=row), patch.object(
            dispatch_service,
            "_preview_channel",
            return_value={"can_generate": True, "blocking_anomalies_count": 0, "totals": ExportTotals(employees_count=2)},
        ):
            result = dispatch_service.get_dispatch_status("co-1", "2025-05")
            assert result.compta.status == "generated"
            assert result.compta.files_count == 2


class TestDispatchCompta:
    def test_raises_when_blocking_anomalies(self):
        with patch.object(
            dispatch_service,
            "_preview_channel",
            return_value={"can_generate": False, "blocking_anomalies_count": 2, "totals": None},
        ):
            with pytest.raises(ValueError, match="anomalies bloquantes"):
                dispatch_service.dispatch_compta(
                    "co-1", "user-1", DispatchComptaRequest(period="2025-05")
                )

    def test_generates_od_and_journal(self):
        with patch.object(
            dispatch_service,
            "_preview_channel",
            return_value={"can_generate": True, "blocking_anomalies_count": 0, "totals": None},
        ), patch.object(
            dispatch_service,
            "_generate_for_channel",
            return_value=(
                ["exp-1", "exp-2"],
                [],
                [],
            ),
        ) as mock_gen, patch.object(
            dispatch_service, "_upsert_dispatch", return_value="disp-1"
        ) as mock_upsert:
            result = dispatch_service.dispatch_compta(
                "co-1", "user-1", DispatchComptaRequest(period="2025-05")
            )
            mock_gen.assert_called_once_with("co-1", "user-1", "compta", "2025-05", "csv")
            mock_upsert.assert_called_once()
            assert result.dispatch_id == "disp-1"
            assert len(result.export_ids) == 2


class TestDispatchBanque:
    def test_generates_virement(self):
        with patch.object(
            dispatch_service,
            "_preview_channel",
            return_value={"can_generate": True, "blocking_anomalies_count": 0, "totals": None},
        ), patch.object(
            dispatch_service,
            "_generate_for_channel",
            return_value=(["exp-v"], [], []),
        ) as mock_gen, patch.object(
            dispatch_service, "_upsert_dispatch", return_value="disp-b"
        ):
            result = dispatch_service.dispatch_banque(
                "co-1",
                "user-1",
                DispatchBanqueRequest(
                    period="2025-05",
                    execution_date="2025-06-05",
                    payment_label="Salaires mai",
                ),
            )
            mock_gen.assert_called_once()
            assert mock_gen.call_args[0][2] == "banque"
            assert result.channel == "banque"


class TestMarkTransmitted:
    def test_not_found_raises(self):
        mock_get = MagicMock()
        mock_get.data = None
        with patch.object(dispatch_service.supabase, "table") as mock_table:
            tbl = MagicMock()
            mock_table.return_value = tbl
            tbl.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value = mock_get
            with pytest.raises(ValueError, match="introuvable"):
                dispatch_service.mark_transmitted("disp-x", "co-1", "user-1")

    def test_updates_status(self):
        mock_get = MagicMock()
        mock_get.data = {"id": "disp-1", "company_id": "co-1"}
        mock_up = MagicMock()
        mock_up.data = [{"id": "disp-1"}]

        with patch.object(dispatch_service.supabase, "table") as mock_table:
            tbl = MagicMock()
            mock_table.return_value = tbl
            tbl.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value = mock_get
            tbl.update.return_value.eq.return_value.eq.return_value.execute.return_value = mock_up

            result = dispatch_service.mark_transmitted("disp-1", "co-1", "user-1", "OK")
            assert result.status == "transmitted"
            assert result.dispatch_id == "disp-1"


class TestChannelSchedules:
    def test_list_defaults_when_empty(self):
        from app.modules.exports.application import scheduled_exports as sched

        with patch.object(sched, "_get_channel_schedule_row", return_value=None):
            result = sched.list_channel_schedules("co-1")
            assert len(result.schedules) == 2
            assert result.schedules[0].channel == "compta"
            assert result.schedules[0].is_active is False

    def test_upsert_creates_schedule(self):
        from app.modules.exports.application import scheduled_exports as sched
        from app.modules.exports.schemas.dispatch import DispatchScheduleUpsert

        ins_row = {
            "id": "sch-1",
            "channel": "compta",
            "name": "Envoi comptabilité",
            "export_type": "od_globale",
            "is_active": True,
            "day_of_month": 5,
            "hour_utc": 6,
            "recipients": [],
            "last_run_at": None,
            "next_run_at": "2025-07-05T06:00:00+00:00",
        }
        mock_ins = MagicMock()
        mock_ins.data = [ins_row]

        with patch.object(sched, "_get_channel_schedule_row", return_value=None), patch.object(
            sched.supabase, "table"
        ) as mock_table:
            tbl = MagicMock()
            mock_table.return_value = tbl
            tbl.insert.return_value.execute.return_value = mock_ins
            out = sched.upsert_channel_schedule(
                "co-1",
                "compta",
                DispatchScheduleUpsert(is_active=True, day_of_month=5, hour_utc=6),
                "user-1",
            )
            assert out.channel == "compta"
            assert out.schedule_id == "sch-1"


class TestRunDueChannelSchedules:
    def test_no_due_schedules(self):
        from app.modules.exports.application import scheduled_exports as sched

        with patch.object(sched, "get_due_channel_schedules", return_value=[]):
            assert sched.run_due_channel_schedules() == []

    def test_runs_due_and_collects_results(self):
        from app.modules.exports.application import scheduled_exports as sched
        from app.modules.exports.schemas.dispatch import DispatchScheduleRunResponse

        due_row = {
            "id": "sch-1",
            "company_id": "co-1",
            "channel": "compta",
            "created_by": "user-1",
        }
        ok_response = DispatchScheduleRunResponse(
            dispatch_id="disp-1",
            export_id="exp-1",
            message="OK",
            parameters={"period": "2025-05"},
        )

        with patch.object(sched, "get_due_channel_schedules", return_value=[due_row]), patch.object(
            sched, "run_channel_schedule_now", return_value=ok_response
        ) as mock_run:
            results = sched.run_due_channel_schedules()
            mock_run.assert_called_once_with("co-1", "compta", "user-1")
            assert results[0]["success"] is True
            assert results[0]["dispatch_id"] == "disp-1"

    def test_skips_row_without_created_by(self):
        from app.modules.exports.application import scheduled_exports as sched

        due_row = {
            "id": "sch-2",
            "company_id": "co-1",
            "channel": "banque",
            "created_by": None,
        }
        with patch.object(sched, "get_due_channel_schedules", return_value=[due_row]):
            results = sched.run_due_channel_schedules()
            assert results[0]["success"] is False
            assert "created_by" in results[0]["error"]
