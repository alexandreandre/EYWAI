"""Tests unitaires — génération PDF avenant au contrat de travail."""

from __future__ import annotations

import io

import pytest

weasyprint = pytest.importorskip("weasyprint")
pdfplumber = pytest.importorskip("pdfplumber")

from app.shared.infrastructure.pdf.avenant import generate_avenant_pdf

_MIN_EMPLOYEE = {
    "first_name": "Marie",
    "last_name": "Martin",
    "hire_date": "2024-03-01",
    "contract_type": "CDI",
    "job_title": "Comptable",
    "adresse": {"rue": "12 rue de la Paix", "code_postal": "69001", "ville": "Lyon"},
    "salaire_de_base": {"valeur": 2800.0},
    "duree_hebdomadaire": 35,
    "lieu_travail": "Lyon centre",
}

_MIN_COMPANY = {
    "company_name": "Alpha SARL",
    "siret": "12345678900012",
    "adresse_rue": "1 avenue Centrale",
    "adresse_code_postal": "75001",
    "adresse_ville": "Paris",
    "city": "Paris",
    "nom_signataire_rh": "Jean Directeur",
    "qualite_signataire_rh": "Directeur général",
}

_AVENANT_TYPES = (
    "avenant_salaire",
    "avenant_poste",
    "avenant_temps",
    "avenant_lieu",
    "avenant_general",
)


def _pdf_text(pdf_bytes: bytes) -> str:
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        return "\n".join(page.extract_text() or "" for page in pdf.pages)


def _base_context(avenant_type: str) -> dict:
    return {
        "type_avenant": avenant_type,
        "date_effet": "2026-06-01",
        "motif": "Évolution interne",
        "ancien_salaire": 2800,
        "nouveau_salaire": 3000,
        "ancien_poste": "Comptable",
        "nouveau_poste": "Comptable senior",
        "ancienne_duree": "35 h",
        "nouvelle_duree": "39 h",
        "ancien_lieu": "Lyon centre",
        "nouveau_lieu": "Paris 8e",
    }


@pytest.mark.parametrize("avenant_type", _AVENANT_TYPES)
def test_generate_avenant_pdf_returns_valid_pdf(avenant_type: str) -> None:
    ctx = _base_context(avenant_type)
    pdf = generate_avenant_pdf(_MIN_EMPLOYEE, _MIN_COMPANY, ctx)
    assert isinstance(pdf, bytes)
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 3000


@pytest.mark.parametrize("avenant_type", _AVENANT_TYPES)
def test_generate_avenant_pdf_contains_mandatory_mentions(avenant_type: str) -> None:
    ctx = _base_context(avenant_type)
    pdf = generate_avenant_pdf(_MIN_EMPLOYEE, _MIN_COMPANY, ctx)
    text = _pdf_text(pdf)
    assert "demeurent inchangées" in text
    assert "Lu et approuvé" in text
    assert "01/06/2026" in text
    assert "Entre les soussignés" in text


def test_generate_avenant_pdf_salaire_shows_old_and_new() -> None:
    ctx = _base_context("avenant_salaire")
    pdf = generate_avenant_pdf(_MIN_EMPLOYEE, _MIN_COMPANY, ctx)
    text = _pdf_text(pdf)
    assert "2 800" in text or "2800" in text
    assert "3 000" in text or "3000" in text


def test_generate_avenant_pdf_economic_motif_note() -> None:
    ctx = _base_context("avenant_salaire")
    ctx["motif"] = "Modification pour motif économique — restructuration"
    pdf = generate_avenant_pdf(_MIN_EMPLOYEE, _MIN_COMPANY, ctx)
    text = _pdf_text(pdf)
    assert "L1222-6" in text or "1222-6" in text
