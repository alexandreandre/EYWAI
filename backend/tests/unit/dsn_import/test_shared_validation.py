"""Tests validation NIR/SIRET partagée."""

from app.shared.dsn_validation import validate_nir, validate_siren, validate_siret


def test_validate_siret_ok():
    ok, err = validate_siret("44306184100047")
    assert ok is True
    assert err is None


def test_validate_siren_ok():
    ok, err = validate_siren("443061841")
    assert ok is True


def test_validate_nir_ok():
    ok, err = validate_nir("180032710123448")
    assert ok is True
