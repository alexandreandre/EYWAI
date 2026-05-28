"""Smoke wiring — module objectives."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


def test_objectives_module_importable():
    from app.modules.objectives.api.router import router

    assert router.prefix == "/api/objectives"
