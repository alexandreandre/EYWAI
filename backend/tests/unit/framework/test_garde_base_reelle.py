"""La garde des tests d'intégration et e2e reconnaît une vraie base Supabase."""

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
