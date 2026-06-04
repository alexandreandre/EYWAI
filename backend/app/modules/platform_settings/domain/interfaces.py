"""Ports domaine platform_settings."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class IPlatformEmailSettingsRepository(ABC):
    @abstractmethod
    def get_row(self) -> Optional[Dict[str, Any]]:
        """Retourne la ligne singleton ou None."""

    @abstractmethod
    def upsert(self, fields: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Crée ou met à jour la ligne singleton."""
