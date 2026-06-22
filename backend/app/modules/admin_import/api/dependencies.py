"""Dépendances FastAPI — import admin (super-admin)."""

from __future__ import annotations

from app.modules.dsn_import.api.dependencies import verify_super_admin

__all__ = ["verify_super_admin"]
