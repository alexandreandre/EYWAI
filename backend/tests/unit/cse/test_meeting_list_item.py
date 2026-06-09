"""Tests unitaires — MeetingListItem enrichi (PV)."""

from datetime import date

from app.modules.cse.infrastructure.cse_service_impl import (
    _build_meeting_list_item,
    _has_minutes_from_meeting,
    _has_minutes_from_recordings,
    _has_pv_text_in_notes,
)


def test_has_pv_text_in_notes_empty():
    assert _has_pv_text_in_notes(None) is False
    assert _has_pv_text_in_notes({}) is False


def test_has_pv_text_in_notes_with_text():
    assert _has_pv_text_in_notes({"pv_text": "Compte rendu"}) is True


def test_has_minutes_from_recordings_pdf():
    assert _has_minutes_from_recordings([{"minutes_pdf_path": "/pv/mtg.pdf"}]) is True


def test_has_minutes_from_meeting_notes_only():
    row = {
        "notes": {"pv_text": "PV rédigé"},
        "cse_meeting_recordings": [],
    }
    assert _has_minutes_from_meeting(row) is True


def test_build_meeting_list_item_with_location_and_minutes():
    row = {
        "id": "mtg-1",
        "title": "CSE mars",
        "meeting_date": "2024-03-15",
        "meeting_time": "14:00:00",
        "location": "Salle A",
        "meeting_type": "ordinaire",
        "status": "terminee",
        "created_at": "2024-03-01T10:00:00",
        "notes": {"pv_text": "Décisions prises"},
        "cse_meeting_participants": {"count": 5},
        "cse_meeting_recordings": [{"minutes_pdf_path": None}],
    }
    item = _build_meeting_list_item(row)
    assert item.location == "Salle A"
    assert item.participant_count == 5
    assert item.has_minutes is True
    assert item.meeting_date == date(2024, 3, 15)
