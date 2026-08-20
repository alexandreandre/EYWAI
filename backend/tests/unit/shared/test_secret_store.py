"""Tests secret_store (chiffrement credentials)."""

import pytest

from app.shared.utils.secret_store import (
    decrypt_secret,
    encrypt_secret,
    has_stored_secret,
)


def test_fernet_key_exige_secret_encryption_key(monkeypatch):
    from app.shared.utils import secret_store

    monkeypatch.delenv("SECRET_ENCRYPTION_KEY", raising=False)
    with pytest.raises(RuntimeError, match="SECRET_ENCRYPTION_KEY"):
        secret_store._fernet_key()


def test_fernet_key_stable_avec_cle_posee(monkeypatch):
    from app.shared.utils import secret_store

    monkeypatch.setenv("SECRET_ENCRYPTION_KEY", "une-phrase-de-test")
    assert secret_store._fernet_key() == secret_store._fernet_key()


def test_decrypt_leve_sans_cle_dediee(monkeypatch):
    """Une clé manquante est une erreur de config visible, pas un None silencieux."""
    monkeypatch.delenv("SECRET_ENCRYPTION_KEY", raising=False)
    ref = "gAAAAA-nimporte-quoi"  # pas de préfixe b64:, chemin Fernet
    with pytest.raises(RuntimeError, match="SECRET_ENCRYPTION_KEY"):
        decrypt_secret(ref)


class TestSecretStore:
    def test_encrypt_decrypt_roundtrip(self, monkeypatch):
        monkeypatch.setenv("SECRET_ENCRYPTION_KEY", "cle-dediee-de-test")
        payload = {"api_key": "secret-value", "api_base_url": "https://api.test"}
        ref = encrypt_secret(payload)
        assert has_stored_secret(ref)
        decrypted = decrypt_secret(ref)
        assert decrypted == payload

    def test_has_stored_secret_false_for_empty(self):
        assert has_stored_secret(None) is False
        assert has_stored_secret("") is False

    def test_decrypt_invalid_returns_none(self, monkeypatch):
        monkeypatch.setenv("SECRET_ENCRYPTION_KEY", "cle-dediee-de-test")
        assert decrypt_secret("not-valid-token") is None
