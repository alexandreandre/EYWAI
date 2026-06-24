"""Tests parse ligne export paie."""

from app.modules.admin_import.application.payroll_export_parser import (
    map_service_to_team_name,
    map_statut_cadre,
    parse_french_date,
    parse_payment_method,
    parse_payroll_export_row,
)


def test_parse_temps_partiel_and_payment():
    mapping = {
        "first_name": "Prénom",
        "last_name": "Nom",
        "activity_pct": "% activité",
        "monthly_hours": "NbHeureMois",
        "payment_method": "Paiement",
        "service": "Service",
        "statut_cadre": "Catégorie TDS",
    }
    row = {
        "Prénom": "Vitor",
        "Nom": "DA SILVA",
        "% activité": "40,00",
        "NbHeureMois": "60,67",
        "Paiement": "Virement",
        "Service": "MOD",
        "Catégorie TDS": "Autre",
    }
    parsed = parse_payroll_export_row(row, mapping)
    patch = parsed["employee_patch"]
    assert patch["is_temps_partiel"] is True
    assert patch["duree_hebdomadaire"] == 14.0
    assert patch["salary_payment_method"] == "virement"
    assert parsed["team_name"] == "MOD"
    assert patch["statut"] == "Non-Cadre"


def test_service_cad_maps_to_moi():
    assert map_service_to_team_name("CAD") == "MOI"
    assert map_service_to_team_name("MOI") == "MOI"
    assert map_service_to_team_name("MOD") == "MOD"


def test_cheque_payment():
    assert parse_payment_method("Chèque") == "cheque"


def test_cadre_statut():
    assert map_statut_cadre("Cadre") == "Cadre"


def test_french_date():
    assert parse_french_date("01/05/2026") == "2026-05-01"


def test_handicap_boeth():
    mapping = {"handicap": "Handicapé", "first_name": "Prénom", "last_name": "Nom"}
    row = {"Handicapé": "Oui", "Prénom": "Théo", "Nom": "LEBRUN"}
    parsed = parse_payroll_export_row(row, mapping)
    assert parsed["boeth"] == {"boeth_code": "01"}


def test_phone_in_email_column_moved_to_phone():
    mapping = {"first_name": "Prénom", "last_name": "Nom", "email": "e-mail", "phone": "Tél"}
    row = {"Prénom": "Lahouari", "Nom": "BOUDJEMAA", "e-mail": "0782385396", "Tél": ""}
    parsed = parse_payroll_export_row(row, mapping)
    assert parsed["preview"]["email"] is None
    assert parsed["preview"]["phone"] == "0782385396"
    assert "email" not in parsed["employee_patch"]
    assert parsed["employee_patch"].get("phone_number") == "0782385396"
