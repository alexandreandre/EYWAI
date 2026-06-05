"""Tests unitaires — complétude de la fiche paie d'un nouveau salarié."""

from datetime import date

from app.modules.onboarding.domain.profile import (
    PAYROLL_REQUIRED_FIELDS,
    is_payroll_eligible,
    is_profile_complete,
    missing_payroll_fields,
    payroll_block_reason,
)


def _complete_employee():
    return {
        "nir": "1850574001234",
        "date_naissance": date(1985, 5, 1),
        "adresse": {"voie": "1 rue de la Paix", "ville": "Paris"},
        "coordonnees_bancaires": {"iban": "FR7612345678901234567890123"},
        "salaire_de_base": {"montant": 2500},
    }


class TestMissingPayrollFields:
    def test_complete_profile_has_no_missing_fields(self):
        assert missing_payroll_fields(_complete_employee()) == []
        assert is_profile_complete(_complete_employee()) is True

    def test_recruitment_hire_minimal_profile_is_incomplete(self):
        # Fiche issue d'une embauche recrutement : état civil/contrat seulement.
        emp = {
            "first_name": "Jean",
            "last_name": "Dupont",
            "job_title": "Dev",
            "hire_date": date(2026, 5, 1),
        }
        missing = missing_payroll_fields(emp)
        assert len(missing) == len(PAYROLL_REQUIRED_FIELDS)
        assert is_profile_complete(emp) is False

    def test_blank_values_count_as_missing(self):
        emp = _complete_employee()
        emp["nir"] = ""
        emp["adresse"] = {}
        emp["coordonnees_bancaires"] = {"iban": None}
        missing = missing_payroll_fields(emp)
        assert "Numéro de sécurité sociale" in missing
        assert "Adresse postale" in missing
        assert "Coordonnées bancaires (RIB)" in missing
        assert "Date de naissance" not in missing

    def test_partial_dict_is_present(self):
        emp = _complete_employee()
        emp["adresse"] = {"ville": "Lyon"}
        assert "Adresse postale" not in missing_payroll_fields(emp)


class TestPayrollEligibility:
    def test_en_onboarding_is_not_payroll_eligible(self):
        emp = {
            "employment_status": "en_onboarding",
            "first_name": "Terence",
            "last_name": "Martin",
        }
        assert is_payroll_eligible(emp) is False
        reason = payroll_block_reason(emp)
        assert reason is not None
        assert "onboarding" in reason.lower()

    def test_actif_incomplete_is_not_payroll_eligible(self):
        emp = {
            "employment_status": "actif",
            "first_name": "Terence",
            "last_name": "Martin",
        }
        assert is_payroll_eligible(emp) is False
        reason = payroll_block_reason(emp)
        assert reason is not None
        assert "incomplète" in reason.lower()

    def test_actif_complete_is_payroll_eligible(self):
        emp = _complete_employee()
        emp["employment_status"] = "actif"
        assert is_payroll_eligible(emp) is True
        assert payroll_block_reason(emp) is None
