"""Tests unitaires — helpers PDF partagés (branding, signataire, montants)."""

from __future__ import annotations

from app.shared.infrastructure.pdf.helpers import (
    clear_logo_cache,
    format_amount_cell,
    format_periode_essai,
    get_company_address,
    get_company_city,
    get_company_signatory,
    get_lieu_travail,
)


def test_get_company_address_from_structured_fields() -> None:
    company = {
        "adresse_rue": "10 rue Centrale",
        "adresse_code_postal": "75001",
        "adresse_ville": "Paris",
    }
    assert get_company_address(company) == "10 rue Centrale, 75001 Paris"
    assert get_company_city(company) == "Paris"


def test_format_periode_essai_from_object() -> None:
    employee = {"periode_essai": {"duree_initiale": 3, "unite": "mois"}}
    text = format_periode_essai(employee)
    assert "3 mois" in text


def test_get_lieu_travail_fallback_to_company_city() -> None:
    employee: dict = {}
    company = {"adresse_ville": "Lyon"}
    assert get_lieu_travail(employee, company) == "Lyon"


def test_get_company_signatory_with_fallback() -> None:
    nom, qualite = get_company_signatory({})
    assert nom == "Le service RH"
    assert qualite == ""

    nom2, qualite2 = get_company_signatory(
        {
            "nom_signataire_rh": "Alice RH",
            "qualite_signataire_rh": "DRH",
        }
    )
    assert nom2 == "Alice RH"
    assert qualite2 == "DRH"


def test_format_amount_cell_neant_when_zero() -> None:
    assert format_amount_cell(0) == "Néant"
    assert "€" in format_amount_cell(1500.0)


def test_resolve_company_logo_returns_none_without_url(monkeypatch) -> None:
    from app.shared.infrastructure.pdf.helpers import resolve_company_logo

    clear_logo_cache()
    assert resolve_company_logo({}) is None
    assert resolve_company_logo({"logo_url": ""}) is None
