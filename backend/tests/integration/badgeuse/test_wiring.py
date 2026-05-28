"""Tests d'intégration badgeuse — squelette (secrets Supabase requis)."""

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.skip(reason="À compléter avec API badgeuse")]


def test_badgeuse_health_placeholder():
    assert True
