"""Tests unitaires génération PDF convocation entretien."""

from datetime import date

from app.modules.annual_reviews.infrastructure.convocation_pdf import (
    generate_convocation_pdf,
)


def test_generate_convocation_pdf_returns_bytes():
    review = {
        "interview_type": "annual_cadres",
        "planned_date": date(2026, 6, 15),
        "year": 2026,
    }
    employee = {
        "first_name": "Jean",
        "last_name": "Dupont",
        "job_title": "Responsable production",
    }
    company = {
        "company_name": "Colorplast",
        "nom_signataire_rh": "Pierre Martin",
        "qualite_signataire_rh": "Directeur Général",
    }
    pdf = generate_convocation_pdf(review, employee, company)
    assert isinstance(pdf, bytes)
    assert pdf[:4] == b"%PDF"
