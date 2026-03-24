"""
Envelope de réponse API générique (success, data, message).

Pour uniformiser les réponses JSON quand on ne suit pas un schéma métier précis.
"""
from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ApiEnvelope(BaseModel, Generic[T]):
    """Réponse API standard : success, data optionnel, message optionnel."""

    success: bool = True
    data: T | None = None
    message: str | None = None


def success_envelope(data: Any = None, message: str | None = None) -> dict[str, Any]:
    """Construit un dictionnaire { success: True, data?, message? }."""
    out: dict[str, Any] = {"success": True}
    if data is not None:
        out["data"] = data
    if message:
        out["message"] = message
    return out


def error_envelope(message: str, data: Any = None) -> dict[str, Any]:
    """Construit un dictionnaire { success: False, message, data? }."""
    out: dict[str, Any] = {"success": False, "message": message}
    if data is not None:
        out["data"] = data
    return out
