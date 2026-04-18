"""Port persistance budget formation."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class AbstractTrainingBudgetRepository(ABC):
    """Accès table training_budget."""

    @abstractmethod
    def get_by_year(self, company_id: str, year: int) -> Optional[Dict[str, Any]]:
        ...

    @abstractmethod
    def get_all(self, company_id: str) -> List[Dict[str, Any]]:
        ...

    @abstractmethod
    def upsert(self, company_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        ...
