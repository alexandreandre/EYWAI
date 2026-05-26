import os

import pytest

from app.modules.badgeuse.application.badge_tokens import (
    build_qr_payload,
    parse_qr_payload,
    verify_qr_payload,
    compute_signature,
)


@pytest.fixture(autouse=True)
def _fixed_secret(monkeypatch):
    monkeypatch.setenv("BADGEUSE_QR_SECRET", "test-secret-key")


def test_build_and_verify_roundtrip():
    salt = "salt-abc-123"
    payload = build_qr_payload(
        company_id="comp-1",
        employee_id="emp-1",
        token_version=2,
        secret_salt=salt,
    )
    parsed = verify_qr_payload(
        payload,
        secret_salt=salt,
        expected_version=2,
    )
    assert parsed is not None
    assert parsed.company_id == "comp-1"
    assert parsed.employee_id == "emp-1"
    assert parsed.token_version == 2


def test_invalid_signature_rejected():
    salt = "salt-abc"
    payload = build_qr_payload(
        company_id="comp-1",
        employee_id="emp-1",
        token_version=1,
        secret_salt=salt,
    )
    tampered = payload[:-3] + "XXX"
    assert (
        verify_qr_payload(tampered, secret_salt=salt, expected_version=1) is None
    )


def test_wrong_version_rejected():
    salt = "salt-abc"
    payload = build_qr_payload(
        company_id="comp-1",
        employee_id="emp-1",
        token_version=1,
        secret_salt=salt,
    )
    assert (
        verify_qr_payload(payload, secret_salt=salt, expected_version=2) is None
    )


def test_parse_invalid_payload():
    assert parse_qr_payload("not-a-qr") is None
    assert parse_qr_payload("") is None


def test_signature_changes_with_salt():
    sig1 = compute_signature(
        company_id="c",
        employee_id="e",
        token_version=1,
        secret_salt="a",
    )
    sig2 = compute_signature(
        company_id="c",
        employee_id="e",
        token_version=1,
        secret_salt="b",
    )
    assert sig1 != sig2
