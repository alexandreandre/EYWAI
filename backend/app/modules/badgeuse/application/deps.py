"""Accès aux dépendances badgeuse via la façade `service` (patchable en tests)."""

from __future__ import annotations

from typing import Any


class _BadgeuseDeps:
    def __getattr__(self, name: str) -> Any:
        from app.modules.badgeuse.application import service

        return getattr(service, name)


deps = _BadgeuseDeps()
