"""Tests secret_store (chiffrement credentials)."""

from app.shared.utils.secret_store import (
    decrypt_secret,
    encrypt_secret,
    has_stored_secret,
)


class TestSecretStore:
    def test_encrypt_decrypt_roundtrip(self):
        payload = {"api_key": "secret-value", "api_base_url": "https://api.test"}
        ref = encrypt_secret(payload)
        assert has_stored_secret(ref)
        decrypted = decrypt_secret(ref)
        assert decrypted == payload

    def test_has_stored_secret_false_for_empty(self):
        assert has_stored_secret(None) is False
        assert has_stored_secret("") is False

    def test_decrypt_invalid_returns_none(self):
        assert decrypt_secret("not-valid-token") is None
