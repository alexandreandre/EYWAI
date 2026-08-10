"""Tests builder DSN depuis bulletin JSON synthétique."""

from __future__ import annotations

from app.modules.dsn_export.application.builder import build_parsed_dsn_from_payroll
from app.modules.dsn_export.domain.writer import encode_dsn_bytes
from app.modules.dsn_import.application.cumuls import extract_monthly_totals
from app.modules.dsn_import.domain.parser import parse_dsn_content


def _sample_company():
    return {
        "siret": "12345678900015",
        "name": "ACME INDUSTRIE",
        "code_naf": "2562B",
        "address": {"rue": "1 RUE DE LA PAIX", "code_postal": "75001", "ville": "PARIS"},
    }


def _sample_employee_row():
    return {
        "employee": {
            "id": "emp-1",
            "first_name": "Jean",
            "last_name": "Dupont",
            "nir": "1850175123456",
            "sexe": "M",
            "date_naissance": "1985-01-15",
            "lieu_naissance": "PARIS",
            "contract_type": "CDI",
            "hire_date": "2020-01-01",
            "statut": "Non-Cadre",
            "adresse": {"rue": "10 AVENUE TEST", "code_postal": "75010", "ville": "PARIS"},
            "matricule": "DUPONT",
            "idcc": "1486",
            "pcs": "389a",
            "job_title": "Technicien",
            "specificites_paie": {
                "mutuelle": {
                    "adhesion": True,
                    "reference_contrat": "CTR-MUT-001",
                    "code_organisme": "ORGPSC01",
                    "option": "E",
                    "population": "841",
                }
            },
        },
        "payslip_data": {
            "salaire_brut": 2500.0,
            "heures_remunerees": 151.67,
            "synthese_net": {
                "net_imposable": 2000.0,
                "net_a_payer": 1850.0,
                "impot_prelevement_a_la_source": {
                    "montant": 100.0,
                    "taux": 5.0,
                    "base": 2000.0,
                },
            },
            "structure_cotisations": {
                "total_salarial": 300.0,
                "total_patronal": 400.0,
                "bloc_principales": [
                    {
                        "coti_id": "securite_sociale_maladie",
                        "libelle": "Sécurité sociale - Maladie",
                        "base": 2500.0,
                        "taux_patronal": 7.0,
                        "montant_patronal": 175.0,
                        "montant_salarial": 0,
                    },
                    {
                        "coti_id": "assurance_chomage",
                        "libelle": "Assurance chômage",
                        "base": 2500.0,
                        "taux_patronal": 4.05,
                        "montant_patronal": 101.25,
                        "montant_salarial": 0,
                    },
                    {
                        "coti_id": "at_mp",
                        "libelle": "AT/MP",
                        "base": 2500.0,
                        "taux_patronal": 1.2,
                        "montant_patronal": 30.0,
                        "montant_salarial": 0,
                    },
                    {
                        "coti_id": "csg_deductible",
                        "libelle": "CSG déductible",
                        "base": 2000.0,
                        "taux_salarial": 6.8,
                        "montant_salarial": 136.0,
                        "montant_patronal": 0,
                    },
                ],
            },
        },
    }


def test_builder_produces_p26_parsable_file():
    dsn_file, warnings = build_parsed_dsn_from_payroll(
        _sample_company(),
        [_sample_employee_row()],
        "2026-01",
    )
    assert dsn_file.envoi.norme == "P26V01"
    assert dsn_file.declaration.mois_principal == "01012026"
    assert len(dsn_file.etablissement.individus) == 1
    ind = dsn_file.etablissement.individus[0]
    assert ind.nir == "1850175123456"
    assert ind.nom == "DUPONT"
    # Le prénom garde la casse de la fiche : le cabinet déclare « Jean ».
    assert ind.prenom == "Jean"
    assert ind.contrats[0].nature == "01"
    totals = extract_monthly_totals(ind)
    assert abs(totals["brut"] - 2500.0) < 0.01
    assert abs(totals["net_imposable"] - 2000.0) < 0.01
    assert abs(totals["pas"] - 100.0) < 0.01
    encoded = encode_dsn_bytes(dsn_file)
    replayed = parse_dsn_content(encoded, file_name="built.dsn")
    assert replayed.dsn_format == "modern"
    assert replayed.envoi.norme == "P26V01"
    assert replayed.etablissement.individus[0].nir == "1850175123456"
    replayed_totals = extract_monthly_totals(replayed.etablissement.individus[0])
    assert abs(replayed_totals["brut"] - 2500.0) < 0.01


def test_builder_maps_modern_cotisation_blocs():
    dsn_file, _ = build_parsed_dsn_from_payroll(
        _sample_company(),
        [_sample_employee_row()],
        "2026-01",
    )
    ver = dsn_file.etablissement.individus[0].contrats[0].versements[0]
    codes = {c.code for c in ver.cotisations_individuelles}
    assert "075" in codes
    assert "040" in codes
    assert "045" in codes
    # La CSG de ce bulletin donne 072 et 079, pas 142 : ce dernier est réservé
    # à la part patronale Agirc-Arrco de tranche 1, absente du jeu d'essai.
    assert "072" in codes
    assert "079" in codes
    assert "142" not in codes
    assert ver.bases_assujetties
    # Une base n'est émise que si une cotisation s'y rattache. Ce jeu d'essai
    # n'a pas de cotisation plafonnée, donc pas de base 02.
    assert any(b.code == "03" for b in ver.bases_assujetties)
    # Chaque cotisation est rattachée à une base réellement émise.
    bases_emises = {b.code for b in ver.bases_assujetties}
    for cotisation in ver.cotisations_individuelles:
        assert cotisation.rubriques["_base"] in bases_emises
