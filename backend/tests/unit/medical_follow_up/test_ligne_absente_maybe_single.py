"""Ligne absente : maybe_single().execute() rend None (postgrest 2.31), la lecture le dit sans planter.

Même piège que la publication des documents de départ (tournage H.4 du 20/10/2026) :
`.data` était lu sur None. Quand la ligne existe, rien ne change.
"""

from __future__ import annotations

import logging

import pytest

from tests.unit.sans_ligne import sans_ligne  # noqa: F401 — fixture

pytestmark = pytest.mark.unit


def test_une_societe_disparue_garde_le_suivi_medical_par_defaut(sans_ligne):
    from app.modules.medical_follow_up.infrastructure import company_contact, providers

    sans_ligne(providers, company_contact, accesseurs=("get_supabase",))
    assert providers.CompanyMedicalSettingsProvider().is_enabled("x") is True
    assert company_contact.get_occupational_health_contact("x") is None
