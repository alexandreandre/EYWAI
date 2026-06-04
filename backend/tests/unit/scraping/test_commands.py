"""
Tests unitaires des commandes scraping (application/commands.py).

Repository et scraper_runner mockés. Couvre execute_scraper, create_schedule,
update_schedule, delete_schedule, mark_alert_as_read, resolve_alert.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.modules.scraping.application.commands import (
    execute_scraper,
    create_schedule,
    update_schedule,
    delete_schedule,
    mark_alert_as_read,
    resolve_alert,
    approve_pending_change,
    reject_pending_change,
    run_tripwire,
)

COMMANDS_MODULE = "app.modules.scraping.application.commands"


def _make_source(
    id="src-1",
    source_key="SMIC",
    source_name="Salaire minimum",
    is_active=True,
    **kwargs,
):
    d = {
        "id": id,
        "source_key": source_key,
        "source_name": source_name,
        "source_type": "legal",
        "is_active": is_active,
        "is_critical": True,
        "orchestrator_path": "scraping/smic/main.py",
        "available_scrapers": ["scraper.py"],
    }
    d.update(kwargs)
    return d


class TestExecuteScraper:
    """Commande execute_scraper."""

    def test_returns_message_source_key_job_id_when_source_active(self):
        source = _make_source()
        mock_repo = MagicMock()
        mock_repo.get_source_by_key.return_value = source
        mock_repo.create_job.return_value = {"id": "job-123"}
        mock_repo.update_job.return_value = None

        with (
            patch(f"{COMMANDS_MODULE}.ScrapingRepository", return_value=mock_repo),
            patch(
                f"{COMMANDS_MODULE}.resolve_script_path",
                return_value=(Path("/fake/script.py"), "orchestrator"),
            ),
        ):
            result = execute_scraper(
                source_key="SMIC",
                scraper_name=None,
                use_orchestrator=True,
                triggered_by="user-1",
                background_task_fn=None,
            )

        mock_repo.get_source_by_key.assert_called_once_with("SMIC")
        mock_repo.create_job.assert_called_once()
        created_data = mock_repo.create_job.call_args[0][0]
        assert created_data["source_id"] == "src-1"
        assert created_data["job_type"] == "manual"
        assert created_data["status"] == "pending"
        assert "started_at" in created_data
        mock_repo.update_job.assert_called_once_with("job-123", {"status": "running"})
        assert result["message"] == "Scraping lancé en arrière-plan"
        assert result["source"] == "Salaire minimum"
        assert result["source_key"] == "SMIC"
        assert result["job_id"] == "job-123"

    def test_calls_background_task_fn_when_provided(self):
        source = _make_source()
        mock_repo = MagicMock()
        mock_repo.get_source_by_key.return_value = source
        mock_repo.create_job.return_value = {"id": "job-456"}
        mock_repo.update_job.return_value = None
        background_calls = []

        def capture_add_task(fn, *args, **kwargs):
            background_calls.append((fn, args, kwargs))

        with (
            patch(f"{COMMANDS_MODULE}.ScrapingRepository", return_value=mock_repo),
            patch(
                f"{COMMANDS_MODULE}.resolve_script_path",
                return_value=(Path("/fake/script.py"), "orchestrator"),
            ),
        ):
            execute_scraper(
                source_key="SMIC",
                triggered_by="user-2",
                background_task_fn=capture_add_task,
            )

        assert len(background_calls) == 1
        fn, args, kwargs = background_calls[0]
        from app.modules.scraping.infrastructure.scraper_runner import (
            run_scraper_script_background,
        )

        assert fn is run_scraper_script_background
        assert args[0] == source
        assert args[1] is None  # scraper_name
        assert args[2] is True  # use_orchestrator
        assert args[3] == "user-2"
        assert args[4] == "job-456"

    def test_raises_when_source_not_found(self):
        mock_repo = MagicMock()
        mock_repo.get_source_by_key.return_value = None

        with patch(f"{COMMANDS_MODULE}.ScrapingRepository", return_value=mock_repo):
            with pytest.raises(ValueError, match="Source non trouvée"):
                execute_scraper(source_key="UNKNOWN", background_task_fn=None)
        mock_repo.create_job.assert_not_called()

    def test_raises_when_source_disabled(self):
        mock_repo = MagicMock()
        mock_repo.get_source_by_key.return_value = _make_source(is_active=False)

        with patch(f"{COMMANDS_MODULE}.ScrapingRepository", return_value=mock_repo):
            with pytest.raises(ValueError, match="Cette source est désactivée"):
                execute_scraper(source_key="SMIC", background_task_fn=None)
        mock_repo.create_job.assert_not_called()


class TestCreateSchedule:
    """Commande create_schedule."""

    def test_returns_success_and_schedule_when_cron_valid(self):
        mock_repo = MagicMock()
        mock_repo.create_schedule.return_value = {
            "id": "sched-1",
            "source_id": "src-1",
            "schedule_type": "cron",
            "cron_expression": "0 0 * * *",
            "is_enabled": True,
        }

        with patch(f"{COMMANDS_MODULE}.ScrapingRepository", return_value=mock_repo):
            result = create_schedule(
                source_id="src-1",
                schedule_type="cron",
                cron_expression="0 0 * * *",
                interval_days=None,
            )

        assert result["success"] is True
        assert result["schedule"]["id"] == "sched-1"
        assert result["schedule"]["schedule_type"] == "cron"
        mock_repo.create_schedule.assert_called_once()
        call_data = mock_repo.create_schedule.call_args[0][0]
        assert call_data["source_id"] == "src-1"
        assert call_data["schedule_type"] == "cron"
        assert call_data["cron_expression"] == "0 0 * * *"
        assert call_data["is_enabled"] is True
        assert "next_run_at" in call_data

    def test_returns_success_when_interval_valid(self):
        mock_repo = MagicMock()
        mock_repo.create_schedule.return_value = {"id": "sched-2", "interval_days": 7}

        with patch(f"{COMMANDS_MODULE}.ScrapingRepository", return_value=mock_repo):
            result = create_schedule(
                source_id="src-1",
                schedule_type="interval",
                cron_expression=None,
                interval_days=7,
            )

        assert result["success"] is True
        call_data = mock_repo.create_schedule.call_args[0][0]
        assert call_data["interval_days"] == 7
        assert "next_run_at" in call_data

    def test_raises_when_cron_without_expression(self):
        with patch(f"{COMMANDS_MODULE}.ScrapingRepository", return_value=MagicMock()):
            with pytest.raises(ValueError, match="Expression cron requise"):
                create_schedule(
                    source_id="src-1",
                    schedule_type="cron",
                    cron_expression=None,
                    interval_days=None,
                )

    def test_raises_when_interval_without_days(self):
        with patch(f"{COMMANDS_MODULE}.ScrapingRepository", return_value=MagicMock()):
            with pytest.raises(ValueError, match="Intervalle en jours requis"):
                create_schedule(
                    source_id="src-1",
                    schedule_type="interval",
                    cron_expression=None,
                    interval_days=None,
                )


class TestUpdateSchedule:
    """Commande update_schedule."""

    def test_returns_success_and_schedule_when_found(self):
        mock_repo = MagicMock()
        mock_repo.update_schedule.return_value = {
            "id": "sched-1",
            "is_enabled": False,
        }

        with patch(f"{COMMANDS_MODULE}.ScrapingRepository", return_value=mock_repo):
            result = update_schedule("sched-1", {"is_enabled": False})

        assert result["success"] is True
        assert result["schedule"]["is_enabled"] is False
        mock_repo.update_schedule.assert_called_once_with(
            "sched-1", {"is_enabled": False}
        )

    def test_raises_when_schedule_not_found(self):
        mock_repo = MagicMock()
        mock_repo.update_schedule.return_value = None

        with patch(f"{COMMANDS_MODULE}.ScrapingRepository", return_value=mock_repo):
            with pytest.raises(ValueError, match="Planification non trouvée"):
                update_schedule("sched-unknown", {"is_enabled": True})

    def test_raises_when_update_data_empty(self):
        with patch(f"{COMMANDS_MODULE}.ScrapingRepository", return_value=MagicMock()):
            with pytest.raises(ValueError, match="Aucune donnée à mettre à jour"):
                update_schedule("sched-1", {})


class TestDeleteSchedule:
    """Commande delete_schedule."""

    def test_returns_success_when_deleted(self):
        mock_repo = MagicMock()
        mock_repo.delete_schedule.return_value = True

        with patch(f"{COMMANDS_MODULE}.ScrapingRepository", return_value=mock_repo):
            result = delete_schedule("sched-1")

        assert result["success"] is True
        assert "supprimée" in result["message"].lower()
        mock_repo.delete_schedule.assert_called_once_with("sched-1")

    def test_raises_when_schedule_not_found(self):
        mock_repo = MagicMock()
        mock_repo.delete_schedule.return_value = False

        with patch(f"{COMMANDS_MODULE}.ScrapingRepository", return_value=mock_repo):
            with pytest.raises(ValueError, match="Planification non trouvée"):
                delete_schedule("sched-unknown")


class TestMarkAlertAsRead:
    """Commande mark_alert_as_read."""

    def test_returns_success_when_marked(self):
        mock_repo = MagicMock()
        mock_repo.mark_alert_read.return_value = True

        with patch(f"{COMMANDS_MODULE}.ScrapingRepository", return_value=mock_repo):
            result = mark_alert_as_read("alert-1")

        assert result["success"] is True
        mock_repo.mark_alert_read.assert_called_once_with("alert-1")

    def test_raises_when_alert_not_found(self):
        mock_repo = MagicMock()
        mock_repo.mark_alert_read.return_value = False

        with patch(f"{COMMANDS_MODULE}.ScrapingRepository", return_value=mock_repo):
            with pytest.raises(ValueError, match="Alerte non trouvée"):
                mark_alert_as_read("alert-unknown")


class TestResolveAlert:
    """Commande resolve_alert."""

    def test_returns_success_when_resolved(self):
        mock_repo = MagicMock()
        mock_repo.resolve_alert.return_value = True

        with patch(f"{COMMANDS_MODULE}.ScrapingRepository", return_value=mock_repo):
            result = resolve_alert(
                "alert-1",
                resolved_by="user-1",
                resolution_note="Corrigé",
            )

        assert result["success"] is True
        mock_repo.resolve_alert.assert_called_once()
        call_args = mock_repo.resolve_alert.call_args[0]
        assert call_args[0] == "alert-1"
        update_data = call_args[1]
        assert update_data["is_resolved"] is True
        assert update_data["is_read"] is True
        assert update_data["resolved_by"] == "user-1"
        assert update_data["resolution_note"] == "Corrigé"
        assert "resolved_at" in update_data

    def test_raises_when_alert_not_found(self):
        mock_repo = MagicMock()
        mock_repo.resolve_alert.return_value = False

        with patch(f"{COMMANDS_MODULE}.ScrapingRepository", return_value=mock_repo):
            with pytest.raises(ValueError, match="Alerte non trouvée"):
                resolve_alert("alert-unknown", resolved_by="user-1")


class TestApprovePendingChange:
    """Commande approve_pending_change (gate de validation humaine)."""

    def test_approves_and_applies(self):
        mock_repo = MagicMock()
        mock_repo.get_pending_change.return_value = {
            "id": "p-1",
            "status": "pending",
            "config_key": "smic",
            "source_id": "src-1",
        }

        with (
            patch(f"{COMMANDS_MODULE}.ScrapingRepository", return_value=mock_repo),
            patch(
                f"{COMMANDS_MODULE}.apply_pending_change_sync",
                return_value={"success": True, "logs": ["ok"], "error": None},
            ) as mock_apply,
        ):
            result = approve_pending_change("p-1", reviewed_by="admin-1")

        assert result["success"] is True
        assert result["pending_id"] == "p-1"
        mock_apply.assert_called_once_with("p-1", reviewed_by="admin-1")
        mock_repo.resolve_review_alerts_for_config.assert_called_once_with(
            config_key="smic",
            source_id="src-1",
            resolved_by="admin-1",
            resolution_note="Changement validé depuis la revue mensuelle.",
        )

    def test_override_value_persisted_before_apply(self):
        mock_repo = MagicMock()
        mock_repo.get_pending_change.return_value = {"id": "p-1", "status": "pending"}

        with (
            patch(f"{COMMANDS_MODULE}.ScrapingRepository", return_value=mock_repo),
            patch(
                f"{COMMANDS_MODULE}.apply_pending_change_sync",
                return_value={"success": True, "logs": [], "error": None},
            ),
        ):
            approve_pending_change(
                "p-1", reviewed_by="admin-1", override_value={"cas_general": 12.0}
            )

        mock_repo.update_pending_change.assert_called_once()
        _, payload = mock_repo.update_pending_change.call_args[0]
        assert payload["proposed_config_data"] == {"cas_general": 12.0}

    def test_raises_when_not_found(self):
        mock_repo = MagicMock()
        mock_repo.get_pending_change.return_value = None

        with patch(f"{COMMANDS_MODULE}.ScrapingRepository", return_value=mock_repo):
            with pytest.raises(ValueError, match="Changement en attente non trouvé"):
                approve_pending_change("p-x", reviewed_by="admin-1")

    def test_raises_when_already_processed(self):
        mock_repo = MagicMock()
        mock_repo.get_pending_change.return_value = {"id": "p-1", "status": "approved"}

        with patch(f"{COMMANDS_MODULE}.ScrapingRepository", return_value=mock_repo):
            with pytest.raises(ValueError, match="déjà été traité"):
                approve_pending_change("p-1", reviewed_by="admin-1")

    def test_raises_when_apply_fails(self):
        mock_repo = MagicMock()
        mock_repo.get_pending_change.return_value = {"id": "p-1", "status": "pending"}

        with (
            patch(f"{COMMANDS_MODULE}.ScrapingRepository", return_value=mock_repo),
            patch(
                f"{COMMANDS_MODULE}.apply_pending_change_sync",
                return_value={"success": False, "logs": [], "error": "boom"},
            ),
        ):
            with pytest.raises(RuntimeError, match="boom"):
                approve_pending_change("p-1", reviewed_by="admin-1")


class TestRejectPendingChange:
    """Commande reject_pending_change."""

    def test_rejects_pending(self):
        mock_repo = MagicMock()
        mock_repo.get_pending_change.return_value = {"id": "p-1", "status": "pending"}
        mock_repo.update_pending_change.return_value = {"id": "p-1", "status": "rejected"}

        with patch(f"{COMMANDS_MODULE}.ScrapingRepository", return_value=mock_repo):
            result = reject_pending_change("p-1", reviewed_by="admin-1", review_note="non")

        assert result["success"] is True
        _, payload = mock_repo.update_pending_change.call_args[0]
        assert payload["status"] == "rejected"
        assert payload["review_note"] == "non"


class TestRunTripwire:
    """Commande run_tripwire (snapshot/diff, sans écriture)."""

    def test_runs_for_all_critical_sources(self):
        mock_repo = MagicMock()
        mock_repo.get_critical_sources.return_value = [
            {"id": "s1", "source_name": "SMIC"},
            {"id": "s2", "source_name": "PSS"},
        ]
        mock_repo.create_job.side_effect = [{"id": "j1"}, {"id": "j2"}]
        calls = []

        with patch(f"{COMMANDS_MODULE}.ScrapingRepository", return_value=mock_repo):
            result = run_tripwire(
                source_key=None,
                triggered_by="admin-1",
                background_task_fn=lambda fn, *a, **k: calls.append((fn, a)),
            )

        assert result["sources_count"] == 2
        assert result["job_ids"] == ["j1", "j2"]
        assert len(calls) == 2
