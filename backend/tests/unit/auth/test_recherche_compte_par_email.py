"""Retrouver un compte par son e-mail parmi TOUS les comptes, pas la première page.

Le 03/11/2026, « Mot de passe oublié » n'envoyait rien à Elsa : la recherche lisait
`auth.admin.list_users()` sans pagination, soit les 50 premiers comptes sur 323. Un
compte au-delà était « inconnu » et l'écran répondait quand même « si cet e-mail
existe, un lien a été envoyé ». Même lecture tronquée dans les groupes de sociétés.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.unit


class _Admin:
    """Imite auth.admin.list_users : 50 comptes par page si per_page n'est pas donné."""

    def __init__(self, n: int):
        self.comptes = [SimpleNamespace(id=f"u{i}", email=f"personne{i}@exemple.fr") for i in range(n)]

    def list_users(self, page=None, per_page=None):
        page, per_page = page or 1, per_page or 50
        return self.comptes[(page - 1) * per_page: page * per_page]


def _client(n: int):
    return SimpleNamespace(auth=SimpleNamespace(admin=_Admin(n)))


def test_mot_de_passe_oublie_trouve_un_compte_au_dela_de_la_premiere_page(monkeypatch):
    from app.modules.auth.infrastructure import providers

    monkeypatch.setattr(providers, "get_supabase_admin_client", lambda: _client(450))
    assert providers.SupabaseAuthProvider().find_user_id_by_email("Personne420@exemple.fr") == "u420"


def test_mot_de_passe_oublie_un_e_mail_inconnu_reste_inconnu(monkeypatch):
    from app.modules.auth.infrastructure import providers

    monkeypatch.setattr(providers, "get_supabase_admin_client", lambda: _client(450))
    assert providers.SupabaseAuthProvider().find_user_id_by_email("absent@exemple.fr") is None


def test_groupes_retrouvent_un_compte_et_tous_les_e_mails(monkeypatch):
    from app.modules.company_groups.infrastructure import user_lookup

    monkeypatch.setattr(user_lookup, "get_supabase_admin_client", lambda: _client(450))
    fournisseur = user_lookup.SupabaseUserLookupProvider()
    assert fournisseur.get_user_by_email("personne300@exemple.fr") == {"id": "u300", "email": "personne300@exemple.fr"}
    assert fournisseur.get_user_emails_map(["u10", "u399"]) == {"u10": "personne10@exemple.fr", "u399": "personne399@exemple.fr"}
