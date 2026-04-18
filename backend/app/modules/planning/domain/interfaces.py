"""Ports persistence du module Planning (sans FastAPI ni accès DB)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, List, Optional


class AbstractPlanningRepository(ABC):
    """Contrat minimal repository Planning (Bloc 2)."""

    @abstractmethod
    def create_shift(self, data: Dict) -> Dict:
        ...

    @abstractmethod
    def get_shift_by_id(self, shift_id: str) -> Optional[Dict]:
        ...

    @abstractmethod
    def get_shifts_by_week(
        self, company_id: str, week_start: str, week_end: str
    ) -> List[Dict]:
        ...

    @abstractmethod
    def lock_week(self, company_id: str, week_start: str, locked_by: str) -> Dict:
        ...
