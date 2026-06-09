"""Tests du resolveur canonique IDCC."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.modules.collective_agreements.application.idcc_resolution import (
    build_convention_collective_payload,
    get_idcc_for_agreement,
    resolve_employee_idcc,
    resolve_minimum_for_classification,
    resolve_minimum_salary_value,
)


class TestResolveEmployeeIdcc:
    def test_priorite_fiche_salarie(self):
        mock_client = MagicMock()
        catalog_resp = MagicMock()
        catalog_resp.data = {"idcc": "3248"}
        mock_client.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = (
            catalog_resp
        )

        idcc = resolve_employee_idcc(
            {"collective_agreement_id": "ag-1"},
            {"id": "co-1", "idcc": "1486"},
            supabase_client=mock_client,
        )
        assert idcc == "3248"

    def test_fallback_company_idcc(self):
        mock_client = MagicMock()
        cc_resp = MagicMock()
        cc_resp.data = []
        mock_client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = (
            cc_resp
        )

        idcc = resolve_employee_idcc(
            {},
            {"id": "co-1", "idcc": "3248"},
            supabase_client=mock_client,
        )
        assert idcc == "3248"

    def test_build_convention_collective_payload(self):
        with patch(
            "app.modules.collective_agreements.application.idcc_resolution.resolve_employee_idcc",
            return_value="3248",
        ):
            payload = build_convention_collective_payload(
                {"collective_agreement_id": "ag-1"},
                {"collective_agreement": "Métallurgie"},
            )
        assert payload == {"idcc": "3248", "libelle": "Métallurgie"}


class TestResolveMinimumForClassification:
    def test_match_par_coefficient(self):
        minima = [
            {"coefficient": 8, "valeur": 2370.83, "libelle": "Classe 8"},
            {"coefficient": 240, "valeur": 2500.0, "libelle": "Syntec 240"},
        ]
        row = resolve_minimum_for_classification(
            minima, {"coefficient": 8, "classe_emploi": 8}
        )
        assert row is not None
        assert row["valeur"] == pytest.approx(2370.83)

    def test_match_par_classe_emploi(self):
        minima = [{"coefficient": 5, "valeur": 2020.83}]
        row = resolve_minimum_for_classification(minima, {"classe_emploi": 5})
        assert row is not None
        assert row["valeur"] == pytest.approx(2020.83)


class TestResolveMinimumSalaryValue:
    @patch(
        "app.modules.collective_agreements.application.idcc_resolution.get_salary_minima_for_agreement"
    )
    def test_retourne_valeur_mensuelle(self, mock_minima):
        mock_minima.return_value = [{"coefficient": 8, "valeur": 2370.83}]
        val = resolve_minimum_salary_value(
            "ag-1",
            {"coefficient": 8},
            code_postal="75001",
        )
        assert val == pytest.approx(2370.83)

    @patch(
        "app.modules.collective_agreements.application.idcc_resolution.get_idcc_for_agreement",
        return_value="3248",
    )
    def test_get_idcc_for_agreement_via_mock(self, _mock):
        mock_client = MagicMock()
        resp = MagicMock()
        resp.data = {"idcc": "3248"}
        mock_client.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = (
            resp
        )
        assert get_idcc_for_agreement("ag-1", mock_client) == "3248"
