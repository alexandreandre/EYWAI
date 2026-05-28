"""
Tests unitaires — is_company_premium (lecture companies.is_premium).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.core.premium import is_company_premium


def _patch_supabase_row(data):
    exec_res = MagicMock()
    exec_res.data = data
    mock_sb = MagicMock()
    mock_sb.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = (
        exec_res
    )
    return mock_sb


def test_t16_is_company_premium_false_when_flag_false() -> None:
    mock_sb = _patch_supabase_row({"is_premium": False})
    with patch("app.core.premium.supabase", mock_sb):
        assert is_company_premium("550e8400-e29b-41d4-a716-446655440000") is False


def test_t17_is_company_premium_true_when_flag_true() -> None:
    mock_sb = _patch_supabase_row({"is_premium": True})
    with patch("app.core.premium.supabase", mock_sb):
        assert is_company_premium("550e8400-e29b-41d4-a716-446655440000") is True


def test_t18_is_company_premium_false_when_data_absent() -> None:
    mock_sb = _patch_supabase_row(None)
    with patch("app.core.premium.supabase", mock_sb):
        assert is_company_premium("550e8400-e29b-41d4-a716-446655440000") is False


def test_is_company_premium_empty_company_id() -> None:
    assert is_company_premium("") is False
