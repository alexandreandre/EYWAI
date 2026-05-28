"""Smoke wiring — module notifications."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


def test_notifications_module_importable():
    from app.modules.notifications.api.router import router

    assert router.prefix == "/api/notifications"
