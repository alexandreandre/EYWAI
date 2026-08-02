"""Tests parse ligne export paie."""

from datetime import date

from app.modules.admin_import.application.payroll_export_parser import (
    resolve_prior_service_months,
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


def test_service_ignored_when_mod_moi_mapping_disabled():
    mapping = {"first_name": "Prénom", "last_name": "Nom", "service": "Service"}
    row = {"Prénom": "A", "Nom": "B", "Service": "MOD"}
    parsed = parse_payroll_export_row(row, mapping, map_mod_moi_teams=False)
    assert parsed["team_name"] is None
    assert parsed["preview"]["service"] == "MOD"
    assert "team_name" not in parsed["preview"]


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


def test_prior_service_months_retranche_anciennete_deja_acquise():
    """La colonne « Nb jour anc. » porte l'ancienneté totale, pas la reprise."""
    # 14 ans de maison, aucune reprise : la colonne vaut l'ancienneté acquise.
    assert (
        resolve_prior_service_months(5236, "2012-04-01", date(2026, 8, 1)) == 0
    )
    # Embauché il y a 2 mois avec 39 mois d'ancienneté reprise d'un précédent contrat.
    assert (
        resolve_prior_service_months(1230, "2026-06-01", date(2026, 8, 1)) == 38
    )
    # Sans date d'embauche connue, on garde la valeur brute plutôt que de la perdre.
    assert resolve_prior_service_months(600, None, date(2026, 8, 1)) == 19
    # Colonne absente ou vide : on ne touche pas au champ.
    assert resolve_prior_service_months(None, "2012-04-01", date(2026, 8, 1)) is None
    assert resolve_prior_service_months(0, "2012-04-01", date(2026, 8, 1)) is None


def test_parse_row_prior_service_months():
    mapping = {
        "first_name": "Prénom",
        "last_name": "Nom",
        "hire_date": "Date entrée",
        "prior_service_days": "Nb jour anc.",
    }
    row = {
        "Prénom": "Michel",
        "Nom": "BOUVEYRON",
        "Date entrée": "01/10/1996",
        "Nb jour anc.": "10860",
    }
    out = parse_payroll_export_row(row, mapping)
    # 10860 j ≈ 362 mois = son ancienneté chez Comitech : aucune reprise à ajouter.
    assert out["employee_patch"]["prior_service_months"] == 0
