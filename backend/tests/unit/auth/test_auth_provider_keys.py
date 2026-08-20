"""Le provider d'auth publique (sign-in/refresh) doit choisir la clé anon par claim JWT."""
import base64
import json

import pytest


def _fake_jwt(role):
    p = base64.urlsafe_b64encode(json.dumps({"role": role}).encode()).rstrip(b"=").decode()
    return f"h.{p}.s"


def test_sign_in_utilise_la_cle_anon(monkeypatch):
    from app.modules.auth.infrastructure import providers as mod

    monkeypatch.setattr(
        "app.core.settings.SUPABASE_URL", "https://x.supabase.co", raising=False
    )
    monkeypatch.setattr(
        "app.core.settings.SUPABASE_KEY", _fake_jwt("service_role"), raising=False
    )
    monkeypatch.setattr(
        "app.core.settings.SUPABASE_SERVICE_KEY", _fake_jwt("anon"), raising=False
    )
    monkeypatch.setattr(
        "app.core.settings.SUPABASE_SERVICE_ROLE_KEY", None, raising=False
    )
    # Constantes figées à l'import du module (jamais une vraie clé dans la sortie pytest)
    monkeypatch.setattr(mod, "SUPABASE_URL", "https://x.supabase.co", raising=False)
    monkeypatch.setattr(mod, "SUPABASE_KEY", _fake_jwt("service_role"), raising=False)

    captured = {}

    def fake_create_client(url, key):
        captured["key"] = key
        raise RuntimeError("stop-ici")  # on n'a besoin que de la clé choisie

    monkeypatch.setattr(mod, "create_client", fake_create_client)
    with pytest.raises(RuntimeError, match="stop-ici"):
        mod.SupabaseAuthProvider().sign_in_with_password("a@b.c", "x")
    assert captured["key"] == _fake_jwt("anon")


def test_refresh_utilise_la_cle_anon(monkeypatch):
    from app.modules.auth.infrastructure import providers as mod

    monkeypatch.setattr(
        "app.core.settings.SUPABASE_URL", "https://x.supabase.co", raising=False
    )
    monkeypatch.setattr(
        "app.core.settings.SUPABASE_KEY", _fake_jwt("service_role"), raising=False
    )
    monkeypatch.setattr(
        "app.core.settings.SUPABASE_SERVICE_KEY", _fake_jwt("anon"), raising=False
    )
    monkeypatch.setattr(
        "app.core.settings.SUPABASE_SERVICE_ROLE_KEY", None, raising=False
    )
    monkeypatch.setattr(mod, "SUPABASE_URL", "https://x.supabase.co", raising=False)
    monkeypatch.setattr(mod, "SUPABASE_KEY", _fake_jwt("service_role"), raising=False)

    captured = {}

    def fake_create_client(url, key):
        captured["key"] = key
        raise RuntimeError("stop-ici")

    monkeypatch.setattr(mod, "create_client", fake_create_client)
    with pytest.raises(RuntimeError, match="stop-ici"):
        mod.SupabaseAuthProvider().refresh_session("un-refresh-token")
    assert captured["key"] == _fake_jwt("anon")
