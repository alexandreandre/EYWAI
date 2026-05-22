"""Tests unitaires — MeetingListItem enrichi (enregistrement / PV)."""

from datetime import date, datetime

from app.modules.cse.infrastructure.cse_service_impl import (
    _build_meeting_list_item,
    _recording_summary_from_nested,
)


def test_recording_summary_empty():
    status, has_minutes = _recording_summary_from_nested(None)
    assert status is None
    assert has_minutes is False


def test_recording_summary_from_list():
    status, has_minutes = _recording_summary_from_nested(
        [{"status": "completed", "minutes_pdf_path": "/pv/mtg.pdf"}]
    )
    assert status == "completed"
    assert has_minutes is True


def test_build_meeting_list_item_with_location_and_recording():
    row = {
        "id": "mtg-1",
        "title": "CSE mars",
        "meeting_date": "2024-03-15",
        "meeting_time": "14:00:00",
        "location": "Salle A",
        "meeting_type": "ordinaire",
        "status": "terminee",
        "created_at": "2024-03-01T10:00:00",
        "cse_meeting_participants": {"count": 5},
        "cse_meeting_recordings": [{"status": "completed", "minutes_pdf_path": None}],
    }
    item = _build_meeting_list_item(row)
    assert item.location == "Salle A"
    assert item.participant_count == 5
    assert item.recording_status == "completed"
    assert item.has_minutes is False
    assert item.meeting_date == date(2024, 3, 15)
