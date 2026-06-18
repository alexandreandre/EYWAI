from __future__ import annotations

import pytest

from app.modules.badgeuse.domain.day_accounting import (
    has_accounting_override,
    override_differs_from_computed,
    resolve_effective_seconds,
)


def test_resolve_effective_seconds_without_override():
    assert resolve_effective_seconds(30600, None) == 30600


def test_resolve_effective_seconds_with_override():
    assert resolve_effective_seconds(30600, 28800) == 28800


def test_has_accounting_override():
    assert has_accounting_override(None) is False
    assert has_accounting_override(28800) is True


def test_override_differs_from_computed():
    assert override_differs_from_computed(30600, None) is False
    assert override_differs_from_computed(30600, 30600) is False
    assert override_differs_from_computed(30600, 28800) is True
