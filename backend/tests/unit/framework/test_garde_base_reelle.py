"""La garde des tests reconnaît une vraie base Supabase et coupe le réseau des unitaires."""

import pytest

from tests._garde_base_reelle import vise_une_vraie_base


@pytest.mark.parametrize(
    "url",
    [
        "https://abcdefghijklmnop.supabase.co",
        "https://ABCDEFGHIJKLMNOP.supabase.co/",
    ],
)
def test_une_base_hebergee_est_reelle(url):
    assert vise_une_vraie_base(url) is True


@pytest.mark.parametrize(
    "url",
    [
        "https://ci-fake.supabase.co",
        "http://localhost:54321",
        "http://127.0.0.1:54321",
        "",
        None,
    ],
)
def test_ce_qui_n_est_pas_une_vraie_base(url):
    assert vise_une_vraie_base(url) is False


def test_la_base_factice_remplace_celle_du_poste(monkeypatch):
    from tests._garde_base_reelle import HOTE_FACTICE_CI, imposer_la_base_factice

    monkeypatch.delenv("MARTINE_TESTS_BASE_REELLE", raising=False)
    monkeypatch.delenv("EYWAI_TESTS_BASE_REELLE", raising=False)
    monkeypatch.setenv("SUPABASE_URL", "https://abcdefghijklmnop.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "vraie-cle")
    imposer_la_base_factice()
    import os

    assert os.environ["SUPABASE_URL"] == f"https://{HOTE_FACTICE_CI}"
    assert os.environ["SUPABASE_SERVICE_ROLE_KEY"] == ""


def test_la_derogation_garde_la_base_jetable(monkeypatch):
    from tests._garde_base_reelle import imposer_la_base_factice

    monkeypatch.setenv("MARTINE_TESTS_BASE_REELLE", "oui")
    monkeypatch.setenv("SUPABASE_URL", "https://jetable.supabase.co")
    imposer_la_base_factice()
    import os

    assert os.environ["SUPABASE_URL"] == "https://jetable.supabase.co"


def test_les_unitaires_n_ont_pas_de_derogation(monkeypatch):
    from tests._garde_base_reelle import refuser_une_vraie_base

    monkeypatch.setenv("MARTINE_TESTS_BASE_REELLE", "oui")
    monkeypatch.setenv("SUPABASE_URL", "https://abcdefghijklmnop.supabase.co")
    with pytest.raises(pytest.exit.Exception, match="pas de dérogation"):
        refuser_une_vraie_base("unitaires", derogation_permise=False)


def test_le_reseau_est_coupe_pendant_un_test_unitaire():
    import socket

    import pytest_socket

    with pytest.raises(pytest_socket.SocketBlockedError):
        socket.create_connection(("ci-fake.supabase.co", 443), timeout=1)
