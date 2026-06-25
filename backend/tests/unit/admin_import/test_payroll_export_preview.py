"""Tests colonnes de prévisualisation export paie."""

from app.modules.admin_import.application.payroll_export_parser import parse_payroll_export_row
from app.modules.admin_import.application.payroll_export_preview import (
    build_preview_field_list,
)


def test_preview_includes_all_mapped_values():
    mapping = {
        "first_name": "Prénom",
        "last_name": "Nom",
        "nir": "Numéro Insee",
        "email": "e-mail",
        "phone": "Tél",
        "nom_usage": "Nom marital",
        "hire_date": "Date d'entrée",
        "base_salary": "Salaire de base",
        "activity_pct": "% activité",
        "monthly_hours": "NbHeureMois",
        "payment_method": "Paiement",
        "service": "Service",
        "statut_cadre": "Catégorie TDS",
        "cdd": "CDD",
        "handicap": "Handicapé",
        "postal_code": "CP",
        "city": "Ville",
    }
    row = {
        "Prénom": "Marie",
        "Nom": "DUPONT",
        "Nom marital": "MARTIN",
        "Numéro Insee": "161099935230854",
        "e-mail": "marie@example.com",
        "Tél": "0612345678",
        "Date d'entrée": "01/03/2024",
        "Salaire de base": "2500,00",
        "% activité": "100",
        "NbHeureMois": "151,67",
        "Paiement": "Virement",
        "Service": "MOD",
        "Catégorie TDS": "Cadre",
        "CDD": "Non",
        "Handicapé": "Non",
        "CP": "75001",
        "Ville": "Paris",
    }
    parsed = parse_payroll_export_row(row, mapping)
    preview = parsed["preview"]

    assert preview["nom_usage"] == "MARTIN"
    assert preview["hire_date"] == "2024-03-01"
    assert preview["base_salary"] == 2500.0
    assert preview["contract_type"] == "CDI"
    assert preview["statut"] == "Cadre"
    assert preview["postal_code"] == "75001"
    assert preview["city"] == "Paris"
    assert preview["handicap"] == "Non"
    assert preview["team_name"] == "MOD"


def test_build_preview_field_list_from_mapping():
    mapping = {"last_name": "Nom", "first_name": "Prénom", "email": "e-mail"}
    rows = [{"preview_columns": {"last_name": "DUPONT", "first_name": "Marie", "email": "a@b.c"}}]
    fields = build_preview_field_list(mapping, rows)
    keys = [f["key"] for f in fields]
    assert "last_name" in keys
    assert "first_name" in keys
    assert "email" in keys
    assert "iban_masked" not in keys
