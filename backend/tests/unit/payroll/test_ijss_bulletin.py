"""Tests calcul CSG IJSS bulletin."""

from __future__ import annotations

import pytest

from app.modules.payroll.engine.ijss_bulletin import compute_ijss_csg_lines


class TestComputeIjssCsgLines:
    def test_brut_448(self):
        lignes, total_csg, net = compute_ijss_csg_lines(
            448.0,
            {"csg_ijss": {"taux_deductible": 0.038, "taux_non_deductible": 0.029}},
        )
        assert len(lignes) == 2
        assert total_csg == pytest.approx(30.01, abs=0.02)
        assert net == pytest.approx(448 - total_csg, 2)

    def test_zero_brut(self):
        lignes, total, net = compute_ijss_csg_lines(0, {})
        assert lignes == []
        assert total == 0
        assert net == 0
