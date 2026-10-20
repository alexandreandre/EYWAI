"""Ligne absente : maybe_single().execute() rend None (postgrest 2.31), la lecture le dit sans planter.

Même piège que la publication des documents de départ (tournage H.4 du 20/10/2026) :
`.data` était lu sur None. Quand la ligne existe, rien ne change.
"""

from __future__ import annotations

import logging

import pytest

from tests.unit.sans_ligne import sans_ligne  # noqa: F401 — fixture

pytestmark = pytest.mark.unit


def test_supprimer_un_objectif_disparu_le_dit(sans_ligne):
    from app.modules.objectives.infrastructure import repository

    sans_ligne(repository)
    with pytest.raises(LookupError, match="Objectif non trouvé"):
        repository.SupabaseObjectivesRepository().delete("x", "c")


def test_supprimer_un_jalon_disparu_le_dit(sans_ligne, monkeypatch):
    from app.modules.objectives.infrastructure import repository

    sans_ligne(repository)
    depot = repository.SupabaseObjectivesRepository()
    monkeypatch.setattr(depot, "_assert_objective", lambda *_a: None)
    with pytest.raises(LookupError, match="Jalon non trouvé"):
        depot.delete_milestone("o", "x", "c")
