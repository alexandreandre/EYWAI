"""Port persistance paramétrage JEI."""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class AbstractJeiSettingsRepository(ABC):
    """Accès table company_jei_settings."""

    @abstractmethod
    def get_by_company(self, company_id: str) -> Optional[Dict[str, Any]]:
        """Retourne la ligne pour company_id ou None."""
        ...

    @abstractmethod
    def upsert(self, company_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Insert ou update sur company_id ; retourne la ligne persistée."""
        ...
