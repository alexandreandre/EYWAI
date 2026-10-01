"""Décision de la mise à jour mensuelle des taux."""

from datetime import datetime, timedelta, timezone

from app.modules.rates.domain.monthly_schedule import (
    StoredMonthlyRun,
    decide_monthly_run,
    describe_monthly_status,
    month_key,
    panel_actions,
    run_button_label,
)

NOW = datetime(2026, 10, 1, 5, 15, tzinfo=timezone.utc)
SOURCES = ("SMIC", "PSS")


def _run(
    status: str,
    *,
    id: str = "run-1",
    age: timedelta = timedelta(minutes=5),
    succeeded: frozenset[str] = frozenset(),
) -> StoredMonthlyRun:
    return StoredMonthlyRun(
        id=id,
        status=status,
        started_at=NOW - age,
        succeeded_source_keys=succeeded,
    )


def test_month_key_uses_paris():
    # 1er octobre 00:30 UTC = 1er octobre 02:30 à Paris (heure d'été).
    assert month_key(datetime(2026, 10, 1, 0, 30, tzinfo=timezone.utc)) == "2026-10"
    # 31 octobre 23:30 UTC = 1er novembre 00:30 à Paris (heure d'hiver).
    assert month_key(datetime(2026, 10, 31, 23, 30, tzinfo=timezone.utc)) == "2026-11"


def test_scheduled_run_starts_on_the_first_when_nothing_exists():
    decision = decide_monthly_run(
        now=NOW,
        auto_enabled=True,
        runs=[],
        all_source_keys=SOURCES,
        scheduled=True,
    )
    assert decision.action == "start"
    assert decision.source_keys == SOURCES


def test_scheduled_run_skips_after_the_third():
    decision = decide_monthly_run(
        now=datetime(2026, 10, 4, 5, 15, tzinfo=timezone.utc),
        auto_enabled=True,
        runs=[],
        all_source_keys=SOURCES,
        scheduled=True,
    )
    assert decision.action == "skip"
    assert "fenêtre" in decision.reason


def test_manual_run_is_allowed_after_the_third():
    decision = decide_monthly_run(
        now=datetime(2026, 10, 15, 8, 0, tzinfo=timezone.utc),
        auto_enabled=True,
        runs=[],
        all_source_keys=SOURCES,
        scheduled=False,
    )
    assert decision.action == "start"


def test_partial_month_retries_only_failed_sources():
    decision = decide_monthly_run(
        now=datetime(2026, 10, 2, 5, 15, tzinfo=timezone.utc),
        auto_enabled=True,
        runs=[_run("partial", succeeded=frozenset({"SMIC"}))],
        all_source_keys=SOURCES,
        scheduled=True,
    )
    assert decision.action == "start"
    assert decision.source_keys == ("PSS",)


def test_fresh_running_run_is_not_started_again():
    decision = decide_monthly_run(
        now=NOW,
        auto_enabled=True,
        runs=[_run("running", id="live")],
        all_source_keys=SOURCES,
        scheduled=True,
    )
    assert decision.action == "skip"
    assert decision.attach_sync_id == "live"


def test_stale_running_run_keeps_sources_already_succeeded():
    decision = decide_monthly_run(
        now=NOW,
        auto_enabled=True,
        runs=[_run("running", id="stuck", age=timedelta(hours=4), succeeded=frozenset({"SMIC"}))],
        all_source_keys=SOURCES,
        scheduled=True,
    )
    assert decision.action == "start"
    assert decision.supersede_run_id == "stuck"
    assert decision.source_keys == ("PSS",)


def test_stale_running_run_is_replaced():
    decision = decide_monthly_run(
        now=NOW,
        auto_enabled=True,
        runs=[_run("running", id="stuck", age=timedelta(hours=4))],
        all_source_keys=SOURCES,
        scheduled=True,
    )
    assert decision.action == "start"
    assert decision.supersede_run_id == "stuck"


def test_force_reruns_everything_including_a_fresh_run():
    decision = decide_monthly_run(
        now=NOW,
        auto_enabled=True,
        runs=[_run("running", id="live", succeeded=frozenset({"SMIC"}))],
        all_source_keys=SOURCES,
        force=True,
        scheduled=False,
    )
    assert decision.action == "start"
    assert decision.source_keys == SOURCES
    assert decision.supersede_run_id == "live"


def test_disabled_switch_blocks_the_schedule_but_not_a_forced_run():
    blocked = decide_monthly_run(
        now=NOW,
        auto_enabled=False,
        runs=[],
        all_source_keys=SOURCES,
        scheduled=True,
    )
    assert blocked.action == "skip"
    forced = decide_monthly_run(
        now=NOW,
        auto_enabled=False,
        runs=[],
        all_source_keys=SOURCES,
        force=True,
    )
    assert forced.action == "start"


def test_completed_month_is_not_repeated():
    decision = decide_monthly_run(
        now=datetime(2026, 10, 2, 5, 15, tzinfo=timezone.utc),
        auto_enabled=True,
        runs=[_run("succeeded", succeeded=frozenset({"SMIC", "PSS"}))],
        all_source_keys=SOURCES,
        scheduled=True,
    )
    assert decision.action == "skip"
    assert "déjà" in decision.reason


def test_status_label_distinguishes_partial_from_total_failure():
    partial = describe_monthly_status(
        NOW,
        enabled=True,
        runs=[_run("partial", succeeded=frozenset({"SMIC"}))],
    )
    assert partial.startswith("Mise à jour partielle")
    failed = describe_monthly_status(NOW, enabled=True, runs=[_run("failed")])
    assert "échoué" in failed
    assert "demain" in failed
    day_three = describe_monthly_status(
        datetime(2026, 10, 3, 5, 15, tzinfo=timezone.utc),
        enabled=True,
        runs=[_run("failed")],
    )
    assert "échoué" not in day_three
    assert "demain" not in day_three
    assert panel_actions(NOW, enabled=True, runs=[_run("partial")]) == (True, True)
    assert run_button_label([_run("partial")]) == "Réessayer les sources en échec"
    assert panel_actions(NOW, enabled=True, runs=[_run("succeeded")]) == (False, True)
