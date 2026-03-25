"""
Ports du domaine residence_permits.

L'application dépend de ces abstractions ; l'infrastructure les implémente.
Compatibles avec les usages employees/dashboard (calculator) et liste (list reader).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class IResidencePermitStatusCalculator(ABC):
    """
    Calcule le statut d'un titre de séjour (valid, to_renew, expired, to_complete).
    Implémentation : infrastructure/providers (domain.rules.calculate_residence_permit_status).
    """

    @abstractmethod
    def calculate_residence_permit_status(
        self,
        is_subject_to_residence_permit: bool,
        residence_permit_expiry_date: Optional[Any],
        employment_status: str,
        reference_date: Optional[Any] = None,
    ) -> Dict[str, Any]:
        pass


class IResidencePermitListReader(ABC):
    """
    Lit la liste des employés soumis au titre de séjour pour une entreprise.
    Filtre : is_subject_to_residence_permit=True, employment_status in ('actif','en_sortie').
    """

    @abstractmethod
    def get_employees_subject_for_company(
        self, company_id: str
    ) -> List[Dict[str, Any]]:
        pass
