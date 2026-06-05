"""Tests unitaires — PDF CSE (convocation, PV)."""

from __future__ import annotations

from app.modules.cse.infrastructure.cse_pdf_impl import (
    generate_convocation_pdf,
    generate_minutes_pdf,
)

_MEETING = {
    "title": "Réunion trimestrielle",
    "meeting_date": "2026-06-15",
    "meeting_time": "14:00",
    "location": "Salle A",
    "meeting_type": "ordinaire",
    "participants": [
        {"first_name": "Jean", "last_name": "Dupont"},
        {"first_name": "Marie", "last_name": "Martin"},
    ],
    "agenda": {"Point 1": "Santé et sécurité", "Point 2": "Informations économiques"},
    "company_data": {
        "company_name": "Test SA",
        "siret": "12345678900012",
        "adresse_rue": "1 rue Test",
        "adresse_code_postal": "75001",
        "adresse_ville": "Paris",
    },
}


def test_generate_convocation_pdf() -> None:
    pdf = generate_convocation_pdf(_MEETING)
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 1500


def test_generate_minutes_pdf_with_signatures() -> None:
    pdf = generate_minutes_pdf(
        _MEETING,
        summary={"key_points": ["Point validé"], "decisions": ["Décision A"]},
    )
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 1500
