"""Tests unitaires du calcul TVA notes de frais."""

import pytest

from app.modules.expenses.domain.vat import (
    compute_vat_breakdown,
    validate_vat_rate,
)


class TestComputeVatBreakdown:
    def test_standard_rate_20(self):
        ht, vat = compute_vat_breakdown(120.0, 20.0)
        assert ht == 100.0
        assert vat == 20.0

    def test_reduced_rate_10(self):
        ht, vat = compute_vat_breakdown(110.0, 10.0)
        assert ht == 100.0
        assert vat == 10.0

    def test_intermediate_rate_5_5(self):
        ht, vat = compute_vat_breakdown(105.5, 5.5)
        assert ht == 100.0
        assert vat == 5.5

    def test_zero_rate(self):
        ht, vat = compute_vat_breakdown(50.0, 0.0)
        assert ht == 50.0
        assert vat == 0.0

    def test_custom_rate(self):
        ht, vat = compute_vat_breakdown(108.0, 8.0)
        assert ht == 100.0
        assert vat == 8.0

    def test_negative_amount_raises(self):
        with pytest.raises(ValueError):
            compute_vat_breakdown(-1.0, 20.0)


class TestValidateVatRate:
    def test_valid_rates(self):
        assert validate_vat_rate(0) is None
        assert validate_vat_rate(20) is None
        assert validate_vat_rate(5.5) is None

    def test_invalid_rates(self):
        assert validate_vat_rate(-1) is not None
        assert validate_vat_rate(101) is not None
