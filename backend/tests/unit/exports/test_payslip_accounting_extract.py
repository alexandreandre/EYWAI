"""Tests extraction comptable depuis payslip_data."""

import pytest

from app.modules.exports.infrastructure.payslip_accounting_extract import (
    extract_cotisations_from_payslip,
    extract_pas_amount,
)

pytestmark = pytest.mark.unit


class TestExtractPasAmount:
    def test_bulletin_format_nested(self):
        assert (
            extract_pas_amount(
                {"impot_prelevement_a_la_source": {"montant": 123.45}}
            )
            == 123.45
        )

    def test_legacy_scalar(self):
        assert extract_pas_amount({"impot_preleve_a_la_source": 50.0}) == 50.0


class TestExtractCotisationsFromPayslip:
    def test_bulletin_blocs_format(self):
        payslip_data = {
            "structure_cotisations": {
                "total_salarial": 600.0,
                "total_patronal": 1200.0,
                "bloc_principales": [
                    {
                        "libelle": "Sécurité sociale",
                        "montant_salarial": 400.0,
                        "montant_patronal": 800.0,
                    },
                    {
                        "libelle": "Retraite",
                        "montant_salarial": 200.0,
                        "montant_patronal": 400.0,
                    },
                ],
            }
        }
        cot_sal, cot_pat, detail, meta = extract_cotisations_from_payslip(payslip_data)
        assert cot_sal == 600.0
        assert cot_pat == 1200.0
        assert len(detail) == 2
        assert meta["format"] == "bulletin_blocs"

    def test_legacy_cotisations_list(self):
        payslip_data = {
            "structure_cotisations": {
                "cotisations": [
                    {"libelle": "URSSAF", "montant_salarial": 100.0, "montant_patronal": 200.0},
                ]
            }
        }
        cot_sal, cot_pat, detail, meta = extract_cotisations_from_payslip(payslip_data)
        assert cot_sal == 100.0
        assert cot_pat == 200.0
        assert len(detail) == 1
        assert meta["format"] == "legacy_cotisations_list"
