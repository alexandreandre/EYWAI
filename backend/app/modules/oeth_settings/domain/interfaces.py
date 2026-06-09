"""Ports repository OETH."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class AbstractOethSettingsRepository(ABC):
    @abstractmethod
    def get_by_company(self, company_id: str) -> Optional[Dict[str, Any]]:
        ...

    @abstractmethod
    def upsert(self, company_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        ...
