"""Variables MARTINE_* lues d'abord, repli sur l'ancien préfixe EYWAI_*."""
from core.env_produit import lire_env


def test_la_nouvelle_variable_l_emporte(monkeypatch):
    monkeypatch.setenv("MARTINE_X_TEST", "neuf")
    monkeypatch.setenv("EYWAI_X_TEST", "ancien")
    assert lire_env("MARTINE_X_TEST") == "neuf"


def test_repli_sur_l_ancienne_variable(monkeypatch):
    monkeypatch.delenv("MARTINE_X_TEST", raising=False)
    monkeypatch.setenv("EYWAI_X_TEST", "ancien")
    assert lire_env("MARTINE_X_TEST") == "ancien"


def test_defaut_si_aucune(monkeypatch):
    monkeypatch.delenv("MARTINE_X_TEST", raising=False)
    monkeypatch.delenv("EYWAI_X_TEST", raising=False)
    assert lire_env("MARTINE_X_TEST", "d") == "d"
