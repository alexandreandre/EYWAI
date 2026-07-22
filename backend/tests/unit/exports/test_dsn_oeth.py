"""Tests export DSN OETH / P26."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.modules.exports.infrastructure.export_dsn import generate_dsn_xml


@patch("app.modules.exports.infrastructure.export_dsn.get_dsn_employees_data")
@patch("app.modules.exports.infrastructure.export_dsn.get_company_data")
@patch("app.modules.exports.infrastructure.export_dsn.oeth_queries")
def test_generate_dsn_includes_boeth(mock_oeth, mock_company, mock_employees):
    mock_company.return_value = {
        "siret": "12345678900015",
        "name": "ACME",
        "code_naf": "6201Z",
        "address": {"rue": "1 rue Test", "code_postal": "75001", "ville": "Paris"},
    }
    mock_employees.return_value = (
        [
            {
                "employee": {
                    "id": "emp-1",
                    "first_name": "Jean",
                    "last_name": "Dupont",
                    "nir": "1850175123456",
                    "sexe": "M",
                    "date_naissance": "1985-01-15",
                    "contract_type": "CDI",
                    "hire_date": "2020-01-01",
                    "statut": "Non-Cadre",
                    "adresse": {
                        "rue": "10 rue Test",
                        "code_postal": "75010",
                        "ville": "Paris",
                    },
                    "boeth_code": "01",
                },
                "payslip": {
                    "payslip_data": {
                        "salaire_brut": 2500,
                        "synthese_net": {
                            "net_imposable": 2000,
                            "net_a_payer": 1900,
                            "impot_prelevement_a_la_source": {
                                "montant": 100,
                                "taux": 5,
                                "base": 2000,
                            },
                        },
                        "structure_cotisations": {
                            "cotisations": [
                                {
                                    "coti_id": "securite_sociale_maladie",
                                    "libelle": "Maladie",
                                    "base": 2500,
                                    "montant_patronal": 175,
                                    "taux_patronal": 7,
                                }
                            ]
                        },
                    }
                },
                "payslip_data": {
                    "salaire_brut": 2500,
                    "synthese_net": {
                        "net_imposable": 2000,
                        "net_a_payer": 1900,
                        "impot_prelevement_a_la_source": {
                            "montant": 100,
                            "taux": 5,
                            "base": 2000,
                        },
                    },
                    "structure_cotisations": {
                        "cotisations": [
                            {
                                "coti_id": "securite_sociale_maladie",
                                "libelle": "Maladie",
                                "base": 2500,
                                "montant_patronal": 175,
                                "taux_patronal": 7,
                            }
                        ]
                    },
                },
                "brut": 2500,
                "net_imposable": 2000,
                "pas": 100,
                "cotisations_detail": [
                    {
                        "coti_id": "securite_sociale_maladie",
                        "libelle": "Maladie",
                        "base": 2500,
                        "montant_patronal": 175,
                        "taux_patronal": 7,
                    }
                ],
            }
        ],
        {},
    )
    mock_oeth.get_boeth_code_for_employee.return_value = "01"
    mock_oeth.get_previous_boeth_for_period.return_value = None
    mock_oeth.build_dsn_payload.return_value = MagicMock(
        complement_oeth=[],
        cotisations_etablissement=[],
        cotisation_agregee=None,
    )

    content = generate_dsn_xml("company-1", "2025-06", "dsn_mensuelle")
    text = content.decode("iso-8859-15")
    assert "P26V01" in text
    assert "S21.G00.40.072,'01'" in text
    assert "S21.G00.30.001,'1850175123456'" in text
    assert "S21.G00.51.011,'001'" in text
