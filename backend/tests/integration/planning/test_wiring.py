"""Smoke wiring — module planning."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


def test_planning_module_importable():
    from app.modules.planning.api.router import router

    assert router.prefix == "/api/planning"
