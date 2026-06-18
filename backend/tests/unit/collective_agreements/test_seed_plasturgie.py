"""Tests seed plasturgie IDCC 0292."""

from __future__ import annotations

from app.modules.collective_agreements.rules.seeds import get_seed
from app.modules.collective_agreements.rules.seeds.plasturgie_0292 import (
    PLASTURGIE_0292_SEED,
)


class TestPlasturgieSeed:
    def test_get_seed_0292(self):
        seed = get_seed("0292")
        assert seed is not None
        assert seed.prime is not None
        assert len(seed.prime.bareme) == 5

    def test_get_seed_alias_1297(self):
        assert get_seed("1297") is PLASTURGIE_0292_SEED

    def test_bareme_paliers(self):
        bareme = PLASTURGIE_0292_SEED.prime.bareme
        taux = {p.annees_min: p.taux for p in bareme}
        assert taux[3] == 0.024
        assert taux[15] == 0.12

    def test_cp_anciennete_seed(self):
        cp = PLASTURGIE_0292_SEED.cp_anciennete
        assert cp is not None
        assert cp.mode == "tier_total"
        assert len(cp.tiers) == 5
