from datetime import datetime, timedelta

from app.modules.badgeuse.domain.time_tracking import (
    TimeEntry,
    TimeEntryType,
    TimeEntrySource,
    compute_day_summary,
    build_sequences_and_anomalies,
)


def _e(ts: str, kind: TimeEntryType) -> TimeEntry:
    return TimeEntry(
        employee_id="e1",
        company_id="c1",
        timestamp=datetime.fromisoformat(ts),
        event_type=kind,
        source=TimeEntrySource.EMPLOYE,
    )


def test_single_complete_sequence():
    entries = [
        _e("2026-03-31T09:00:00", TimeEntryType.ENTREE),
        _e("2026-03-31T12:00:00", TimeEntryType.SORTIE),
    ]
    summary = compute_day_summary(entries)
    assert summary.total_duration == timedelta(hours=3)
    assert len(summary.sequences) == 1
    assert not summary.anomalies


def test_two_sequences_with_pause():
    entries = [
        _e("2026-03-31T09:00:00", TimeEntryType.ENTREE),
        _e("2026-03-31T12:00:00", TimeEntryType.SORTIE),
        _e("2026-03-31T13:00:00", TimeEntryType.ENTREE),
        _e("2026-03-31T17:00:00", TimeEntryType.SORTIE),
    ]
    summary = compute_day_summary(entries)
    assert summary.total_duration == timedelta(hours=7)
    assert len(summary.sequences) == 2
    assert not summary.anomalies


def test_anomaly_entry_without_exit():
    entries = [
        _e("2026-03-31T09:00:00", TimeEntryType.ENTREE),
    ]
    sequences, anomalies = build_sequences_and_anomalies(entries)
    assert not sequences
    assert len(anomalies) == 1
    assert "Entrée sans sortie" in anomalies[0].message


def test_anomaly_exit_without_entry():
    entries = [
        _e("2026-03-31T12:00:00", TimeEntryType.SORTIE),
    ]
    sequences, anomalies = build_sequences_and_anomalies(entries)
    assert not sequences
    assert len(anomalies) == 1
    assert "Sortie sans entrée" in anomalies[0].message


def test_anomaly_double_entry():
    entries = [
        _e("2026-03-31T09:00:00", TimeEntryType.ENTREE),
        _e("2026-03-31T10:00:00", TimeEntryType.ENTREE),
    ]
    sequences, anomalies = build_sequences_and_anomalies(entries)
    assert len(anomalies) == 1
    assert "Deux entrées consécutives" in anomalies[0].message


def test_anomaly_exit_before_entry():
    entries = [
        _e("2026-03-31T10:00:00", TimeEntryType.SORTIE),
        _e("2026-03-31T11:00:00", TimeEntryType.ENTREE),
    ]
    # l'ordre sera ENTREE puis SORTIE après tri, mais l'anomalie SORTIE sans ENTREE
    sequences, anomalies = build_sequences_and_anomalies(entries)
    # selon les règles, seule la séquence valide est comptée, les anomalies sont listées
    assert anomalies
