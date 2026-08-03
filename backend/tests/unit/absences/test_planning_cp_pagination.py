"""PostgREST plafonne une lecture à 1 000 lignes, sans le signaler.

Le planning de paie dépasse ce seuil dès qu'une société un peu grosse a douze
mois d'historique : Cartol compte 1 144 lignes. Sans pagination, les congés
payés des derniers salariés disparaissaient des compteurs sans erreur.
"""

from __future__ import annotations

from app.modules.absences.infrastructure.pagination import fetch_all_rows


def test_lit_toutes_les_pages():
    source = [{"n": i} for i in range(2500)]

    def page(offset: int, limit: int):
        return source[offset : offset + limit]

    assert fetch_all_rows(page, page_size=1000) == source


def test_sarrete_sur_une_page_incomplete():
    source = [{"n": i} for i in range(1500)]
    appels: list[tuple[int, int]] = []

    def page(offset: int, limit: int):
        appels.append((offset, limit))
        return source[offset : offset + limit]

    assert len(fetch_all_rows(page, page_size=1000)) == 1500
    assert appels == [(0, 1000), (1000, 1000)]


def test_source_vide():
    assert fetch_all_rows(lambda offset, limit: [], page_size=1000) == []


def test_taille_exactement_multiple_de_la_page():
    source = [{"n": i} for i in range(2000)]

    def page(offset: int, limit: int):
        return source[offset : offset + limit]

    assert len(fetch_all_rows(page, page_size=1000)) == 2000
