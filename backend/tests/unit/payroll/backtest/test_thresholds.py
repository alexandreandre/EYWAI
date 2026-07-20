"""Tests seuils intelligents."""

import pytest

from app.modules.payroll.backtest.thresholds import ThresholdConfig, default_thresholds

pytestmark = pytest.mark.unit


class TestThresholds:
    def test_tier_s_floor(self):
        cfg = default_thresholds()
        assert cfg.tolerance("S", 3000) == 0.01

    def test_tier_b_relative(self):
        cfg = default_thresholds()
        tol = cfg.tolerance("B", 5000)
        assert tol >= 0.02
        assert tol >= 5000 * 0.0002  # 0.02%

    def test_aggregate_budget(self):
        cfg = default_thresholds()
        assert cfg.aggregate_rounding_budget(35) == pytest.approx(0.185, abs=0.001)

    def test_known_gap_fields(self):
        cfg = default_thresholds()
        assert "cumuls_annuels" in cfg.known_gap_fields
