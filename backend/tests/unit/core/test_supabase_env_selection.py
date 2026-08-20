"""Tests de la sélection role-aware des clés Supabase (clés forgées, aucun vrai secret)."""
import base64
import json

import pytest

from app.core import settings


def _fake_jwt(role: str) -> str:
    header = base64.urlsafe_b64encode(b'{"alg":"HS256"}').rstrip(b"=").decode()
    payload = base64.urlsafe_b64encode(
        json.dumps({"role": role}).encode()
    ).rstrip(b"=").decode()
    return f"{header}.{payload}.sig"


ANON = _fake_jwt("anon")
SERVICE = _fake_jwt("service_role")


def test_anon_env_prefere_la_cle_anon_meme_inversee(monkeypatch):
    # État actuel de prod : SUPABASE_KEY = service_role, SUPABASE_SERVICE_KEY = anon
    monkeypatch.setattr(settings, "SUPABASE_URL", "https://x.supabase.co")
    monkeypatch.setattr(settings, "SUPABASE_KEY", SERVICE)
    monkeypatch.setattr(settings, "SUPABASE_SERVICE_KEY", ANON)
    monkeypatch.setattr(settings, "SUPABASE_SERVICE_ROLE_KEY", None)
    url, key = settings.get_supabase_anon_env()
    assert key == ANON


def test_anon_env_apres_bascule(monkeypatch):
    # État cible : SUPABASE_KEY = anon, SUPABASE_SERVICE_KEY = service_role
    monkeypatch.setattr(settings, "SUPABASE_URL", "https://x.supabase.co")
    monkeypatch.setattr(settings, "SUPABASE_KEY", ANON)
    monkeypatch.setattr(settings, "SUPABASE_SERVICE_KEY", SERVICE)
    monkeypatch.setattr(settings, "SUPABASE_SERVICE_ROLE_KEY", None)
    url, key = settings.get_supabase_anon_env()
    assert key == ANON


def test_anon_env_repli_si_roles_indecodables(monkeypatch):
    monkeypatch.setattr(settings, "SUPABASE_URL", "https://x.supabase.co")
    monkeypatch.setattr(settings, "SUPABASE_KEY", "pas-un-jwt")
    monkeypatch.setattr(settings, "SUPABASE_SERVICE_KEY", None)
    monkeypatch.setattr(settings, "SUPABASE_SERVICE_ROLE_KEY", None)
    url, key = settings.get_supabase_anon_env()
    assert key == "pas-un-jwt"


def test_admin_env_prefere_service_role_dans_les_deux_etats(monkeypatch):
    monkeypatch.setattr(settings, "SUPABASE_URL", "https://x.supabase.co")
    for cfg in [(SERVICE, ANON), (ANON, SERVICE)]:
        monkeypatch.setattr(settings, "SUPABASE_KEY", cfg[0])
        monkeypatch.setattr(settings, "SUPABASE_SERVICE_KEY", cfg[1])
        monkeypatch.setattr(settings, "SUPABASE_SERVICE_ROLE_KEY", None)
        url, key = settings.get_supabase_admin_env()
        assert key == SERVICE
