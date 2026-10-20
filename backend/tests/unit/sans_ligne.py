"""Client PostgREST doublé : `maybe_single()` sans ligne rend None.

Avec postgrest 2.31, `.maybe_single().execute()` renvoie None (et non une
réponse à `data` vide) quand aucune ligne ne correspond ; lire `.data` dessus
lève AttributeError (publication des documents de départ, tournage H.4 du
20/10/2026). Ce double rejoue ce cas pour toute table ; les autres requêtes
rendent la ligne ou la liste fournie pour leur table.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest


class _Requete:
    """Toute la chaîne (select, eq, order, not_, limit…) rend la requête."""

    def __init__(self, client: "ClientSansLigne", table: str) -> None:
        self._client = client
        self._table = table
        self._maybe_single = False

    def maybe_single(self, *_a, **_k) -> "_Requete":
        self._maybe_single = True
        return self

    def execute(self, *_a, **_k):
        self._client.lues.append(self._table)
        if self._maybe_single:
            return None
        return SimpleNamespace(data=self._client.lignes.get(self._table, []))

    def __call__(self, *_a, **_k) -> "_Requete":
        return self

    def __getattr__(self, _nom: str) -> "_Requete":
        return self


class ClientSansLigne:
    def __init__(self, lignes: dict[str, Any] | None = None) -> None:
        self.lignes = lignes or {}
        self.lues: list[str] = []

    def table(self, nom: str, *_a, **_k) -> _Requete:
        return _Requete(self, nom)

    from_ = table


@pytest.fixture
def sans_ligne(monkeypatch):
    """Pose le client doublé partout où les modules le prennent ; rend une
    fonction qui le pose aussi sur les modules passés (attribut `supabase` ou
    accesseur nommé)."""
    from app.core import database

    client = ClientSansLigne()
    monkeypatch.setattr(database, "supabase", client, raising=False)
    monkeypatch.setattr(database, "get_supabase_client", lambda *_a, **_k: client, raising=False)
    monkeypatch.setattr(database, "get_supabase_admin_client", lambda *_a, **_k: client, raising=False)

    def poser(*modules, accesseurs: tuple[str, ...] = (), lignes: dict | None = None):
        if lignes:
            client.lignes.update(lignes)
        for module in modules:
            if hasattr(module, "supabase"):
                monkeypatch.setattr(module, "supabase", client)
            for nom in accesseurs:
                if hasattr(module, nom):
                    monkeypatch.setattr(module, nom, lambda *_a, **_k: client)
        return client

    return poser
