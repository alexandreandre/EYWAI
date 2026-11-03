"""Parcourir tous les comptes de connexion (auth.users), page par page.

`auth.admin.list_users()` sans argument ne rend que la première page (50 comptes) :
toute recherche par e-mail doit passer par ici.
"""

from __future__ import annotations

from typing import Any, Iterator

PAR_PAGE = 200


def tous_les_comptes(admin_client: Any) -> Iterator[Any]:
    page = 1
    while True:
        lot = admin_client.auth.admin.list_users(page=page, per_page=PAR_PAGE) or []
        yield from lot
        if len(lot) < PAR_PAGE:
            return
        page += 1
