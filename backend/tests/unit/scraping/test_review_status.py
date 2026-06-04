"""Tests du filtrage validations / alertes déjà traitées."""

from app.modules.scraping.application.review_status import (
    config_data_matches,
    filter_actionable_alerts,
    filter_actionable_pending,
    pending_requires_action,
    review_alert_requires_action,
)


def test_pending_not_actionable_when_proposed_matches_active():
    pending = {
        "status": "pending",
        "config_key": "smic",
        "persistence_mode": "full",
        "proposed_config_data": {"cas_general": 11.88, "annee": 2026},
    }
    active = {"config_data": {"cas_general": 11.88, "annee": 2026}}
    assert pending_requires_action(pending, active) is False


def test_pending_actionable_when_values_differ():
    pending = {
        "status": "pending",
        "config_key": "smic",
        "persistence_mode": "full",
        "proposed_config_data": {"cas_general": 12.00, "annee": 2026},
    }
    active = {"config_data": {"cas_general": 11.88, "annee": 2026}}
    assert pending_requires_action(pending, active) is True


def test_cotisations_pending_ignores_last_checked_at():
    pending = {
        "status": "pending",
        "config_key": "cotisations",
        "persistence_mode": "cotisations",
        "proposed_config_data": {
            "cotisations": [{"id": "csg", "salarial": 0.029}]
        },
    }
    active = {
        "config_data": {
            "cotisations": [
                {"id": "csg", "salarial": 0.029, "last_checked_at": "2026-01-01"}
            ]
        }
    }
    assert config_data_matches(
        persistence_mode="cotisations",
        current_data=active["config_data"],
        proposed_data=pending["proposed_config_data"],
    )
    assert pending_requires_action(pending, active) is False


def test_filter_actionable_pending_excludes_stale_rows():
    rows = [
        {
            "id": "p-1",
            "status": "pending",
            "config_key": "smic",
            "persistence_mode": "full",
            "proposed_config_data": {"v": 1},
        },
        {
            "id": "p-2",
            "status": "pending",
            "config_key": "pss",
            "persistence_mode": "full",
            "proposed_config_data": {"v": 2},
        },
    ]
    active = {
        "smic": {"config_data": {"v": 1}},
        "pss": {"config_data": {"v": 1}},
    }
    filtered = filter_actionable_pending(rows, active)
    assert [row["id"] for row in filtered] == ["p-2"]


def test_review_alert_hidden_after_approval():
    alert = {
        "id": "a-1",
        "alert_type": "review_required",
        "created_at": "2026-06-01T10:00:00+00:00",
        "details": {"config_key": "smic"},
    }
    latest_approved = {
        "smic": {
            "applied_at": "2026-06-01T11:00:00+00:00",
            "proposed_config_data": {"v": 2},
        }
    }
    assert (
        review_alert_requires_action(
            alert,
            pending_rows=[],
            active_configs={"smic": {"config_data": {"v": 2}}},
            latest_approved=latest_approved,
        )
        is False
    )


def test_review_alert_kept_when_pending_still_actionable():
    alert = {
        "id": "a-1",
        "alert_type": "review_required",
        "created_at": "2026-06-01T10:00:00+00:00",
        "details": {"config_key": "smic"},
    }
    pending = [
        {
            "status": "pending",
            "config_key": "smic",
            "persistence_mode": "full",
            "proposed_config_data": {"v": 2},
        }
    ]
    active = {"smic": {"config_data": {"v": 1}}}
    assert (
        review_alert_requires_action(
            alert,
            pending_rows=pending,
            active_configs=active,
            latest_approved={},
        )
        is True
    )


def test_review_alert_hidden_when_stale_pending_matches_active():
    alert = {
        "id": "a-1",
        "alert_type": "review_required",
        "created_at": "2026-06-01T10:00:00+00:00",
        "details": {"config_key": "smic"},
    }
    pending = [
        {
            "status": "pending",
            "config_key": "smic",
            "persistence_mode": "full",
            "proposed_config_data": {"v": 1},
        }
    ]
    active = {"smic": {"config_data": {"v": 1}}}
    filtered = filter_actionable_alerts(
        [alert],
        pending_rows=pending,
        active_configs=active,
        latest_approved={},
    )
    assert filtered == []
