"""Ligne absente : maybe_single().execute() rend None (postgrest 2.31), la lecture le dit sans planter.

Même piège que la publication des documents de départ (tournage H.4 du 20/10/2026) :
`.data` était lu sur None. Quand la ligne existe, rien ne change.
"""

from __future__ import annotations

import logging

import pytest

from tests.unit.sans_ligne import sans_ligne  # noqa: F401 — fixture

pytestmark = pytest.mark.unit


def test_une_prime_disparue_se_lit_comme_absente(sans_ligne):
    from app.modules.bonus_types.infrastructure import repository

    sans_ligne(repository)
    assert repository.SupabaseBonusTypeRepository().get_by_id("x", "c") is None


def test_un_mois_sans_calendrier_n_a_aucune_heure(sans_ligne):
    from app.modules.bonus_types.infrastructure import providers

    sans_ligne(providers)
    assert providers.SupabaseEmployeeHoursProvider().get_total_actual_hours("e", 2026, 10) == 0.0
