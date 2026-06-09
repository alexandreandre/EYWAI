"""Tests enrichissement payload simulation (CC + classification)."""

from __future__ import annotations

from unittest.mock import patch

from app.modules.payroll.application.simulation_queries import (
    company_to_payroll_payload,
    employee_to_payroll_payload,
    manual_employee_payload,
)


class TestSimulationPayloadCc:
    def test_employee_payload_inclut_cc_et_classification(self):
        employee = {
            "id": "e1",
            "first_name": "Jean",
            "last_name": "Dupont",
            "statut": "Non-cadre",
            "duree_hebdomadaire": 35,
            "hire_date": "2020-03-01",
            "salaire_de_base": {"valeur": 2500},
            "classification_conventionnelle": {
                "groupe_emploi": "B",
                "classe_emploi": 5,
                "coefficient": 5,
            },
            "collective_agreement_id": "ag-metallurgie",
        }
        company = {
            "id": "co-1",
            "name": "ACME",
            "adresse_code_postal": "77000",
            "idcc": "3248",
            "collective_agreement": "Métallurgie",
        }
        with patch(
            "app.modules.payroll.application.simulation_queries.build_convention_collective_payload",
            return_value={"idcc": "3248", "libelle": "Métallurgie"},
        ):
            payload = employee_to_payroll_payload(employee, company)

        assert payload["date_entree"] == "2020-03-01"
        assert payload["convention_collective"]["idcc"] == "3248"
        assert payload["classification_conventionnelle"]["classe_emploi"] == 5

    def test_manual_payload_inclut_idcc_et_grade(self):
        options = {
            "salaire_base_override": 2400,
            "manual_params": {
                "statut": "Non-cadre",
                "collective_agreement_id": "ag-1",
                "idcc": "3248",
                "classification_conventionnelle": {
                    "groupe_emploi": "B",
                    "classe_emploi": 5,
                    "coefficient": 5,
                },
                "date_entree": "2019-01-15",
            },
        }
        payload = manual_employee_payload(options, {"collective_agreement": "Métallurgie"})
        assert payload["id"] == "manual"
        assert payload["convention_collective"]["idcc"] == "3248"
        assert payload["classification_conventionnelle"]["coefficient"] == 5
        assert payload["date_entree"] == "2019-01-15"

    def test_company_payload_inclut_code_postal(self):
        company = {
            "name": "ACME",
            "adresse_code_postal": "77000",
            "adresse_ville": "Melun",
            "effectif": 42,
            "idcc": "3248",
        }
        payload = company_to_payroll_payload(company)
        assert payload["adresse_code_postal"] == "77000"
        assert payload["parametres_paie"]["idcc"] == "3248"
        assert payload["identification"]["adresse"]["code_postal"] == "77000"
