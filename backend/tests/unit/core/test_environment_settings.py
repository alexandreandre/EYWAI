"""Environnement d'exécution : APP_ENV, redirection e-mail, origines CORS."""

import importlib

import pytest

from app.core import settings


def test_app_env_defaut_est_prod():
    assert settings.APP_ENV == "prod"
    assert settings.is_test_environment() is False


def test_is_test_environment_vrai_quand_app_env_test(monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "test")
    assert settings.is_test_environment() is True


def test_check_environment_consistency_ok_en_prod(monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "prod")
    monkeypatch.setattr(settings, "EMAIL_FORCE_REDIRECT_TO", None)
    settings.check_environment_consistency()  # ne lève pas


def test_check_environment_consistency_refuse_test_sans_redirection(monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "test")
    monkeypatch.setattr(settings, "EMAIL_FORCE_REDIRECT_TO", None)
    with pytest.raises(RuntimeError, match="EMAIL_FORCE_REDIRECT_TO"):
        settings.check_environment_consistency()


def test_check_environment_consistency_ok_test_avec_redirection(monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "test")
    monkeypatch.setattr(settings, "EMAIL_FORCE_REDIRECT_TO", "test@eywai.fr")
    settings.check_environment_consistency()  # ne lève pas


@pytest.mark.parametrize(
    "raw,attendu",
    [
        (None, []),
        ("", []),
        ("   ", []),
        ("https://a.run.app", ["https://a.run.app"]),
        (
            "https://a.run.app,https://b.run.app",
            ["https://a.run.app", "https://b.run.app"],
        ),
        (
            " https://a.run.app , , https://b.run.app ",
            ["https://a.run.app", "https://b.run.app"],
        ),
    ],
)
def test_parse_extra_origins(raw, attendu):
    assert settings.parse_extra_origins(raw) == attendu


def test_origines_extra_vides_par_defaut():
    assert settings.ALLOWED_ORIGINS_EXTRA == []


def test_origines_extra_ajoutees_sans_toucher_aux_origines_de_prod(monkeypatch):
    monkeypatch.setenv("ALLOWED_ORIGINS_EXTRA", "https://sirh-frontend-test.run.app")
    importlib.reload(settings)
    try:
        assert settings.ALLOWED_ORIGINS_EXTRA == ["https://sirh-frontend-test.run.app"]
    finally:
        monkeypatch.delenv("ALLOWED_ORIGINS_EXTRA", raising=False)
        importlib.reload(settings)
