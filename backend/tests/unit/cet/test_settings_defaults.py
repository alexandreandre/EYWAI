"""Tests defaults CET v2."""

from app.modules.cet.application.queries import settings_to_api


def test_settings_defaults_hs_on_cp_off():
    row = {
        "company_id": "co-1",
        "cet_enabled": False,
    }
    api = settings_to_api(row)
    assert api["allow_deposit_hs"] is True
    assert api["allow_deposit_cp"] is False
    assert api["cp_unit"] == "ouvrables"
    assert api["cp_debit_timing"] == "on_validation"
    assert api["hs_debit_timing"] == "on_payroll"
    assert api["max_cp_days_per_year"] is None


def test_settings_cartol_like_example():
    row = {
        "company_id": "co-cartol",
        "cet_enabled": True,
        "allow_deposit_hs": True,
        "allow_deposit_cp": True,
        "max_cp_days_per_year": 10,
        "cp_unit": "ouvres",
        "ouvres_to_ouvrables_ratio": 1.2,
        "cp_debit_timing": "on_validation",
        "validation_mode": "manager",
    }
    api = settings_to_api(row)
    assert api["max_cp_days_per_year"] == 10.0
    assert api["cp_unit"] == "ouvres"
    assert api["validation_mode"] == "manager"
