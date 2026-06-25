"""Tests détection colonnes export paie Quadra."""

from app.modules.admin_import.application.payroll_export_mapping import (
    detect_payroll_export_column_mapping,
    normalize_nir,
)

HEADERS_ELSA = [
    "Numéro",
    "Identifiant",
    "Nom",
    "Nom marital",
    "Prénom",
    "N°",
    "BTQ",
    "Voie",
    "Complément",
    "CP",
    "Ville",
    "Étab.",
    "Service",
    "Tél",
    "Tél 2",
    "e-mail",
    "Envoi par mail",
    "Date Naiss",
    "Dept Naiss",
    "Commune Naissance",
    "Etranger",
    "Nationalité",
    "Type nationalité",
    "Numéro Insee",
    "Sexe",
    "Situation",
    "Nb Enfants",
    "RegimeSS",
    "Paiement",
    "RIB",
    "Catégorie TDS",
    "Code CIPDZ",
    "CDD",
    "Handicapé",
    "Date d'entrée",
    "% activité",
    "NbHeureMois",
    "Salaire de base",
]


def test_detect_quadra_headers():
    mapping = detect_payroll_export_column_mapping(HEADERS_ELSA)
    assert mapping["nir"] == "Numéro Insee"
    assert mapping["last_name"] == "Nom"
    assert mapping["first_name"] == "Prénom"
    assert mapping["nom_usage"] == "Nom marital"
    assert mapping["identifiant"] == "Identifiant"
    assert mapping["street_num"] == "N°"
    assert "Numéro" not in mapping.values()
    assert mapping["email"] == "e-mail"
    assert mapping["service"] == "Service"
    assert mapping["payment_method"] == "Paiement"
    assert mapping["rib"] == "RIB"
    assert mapping["handicap"] == "Handicapé"
    assert mapping["activity_pct"] == "% activité"
    assert mapping["monthly_hours"] == "NbHeureMois"
    assert mapping["base_salary"] == "Salaire de base"
    assert mapping["hire_date"] == "Date d'entrée"
    assert mapping["statut_cadre"] == "Catégorie TDS"
    assert mapping["cdd"] == "CDD"
    assert mapping["postal_code"] == "CP"
    assert mapping["city"] == "Ville"


def test_normalize_nir():
    assert normalize_nir("161 099 935 230 854") == "161099935230854"
