"""
Repository residence_permits : implémentation de IResidencePermitListReader.

Délègue aux queries infrastructure. Aucune entité persistée dans ce module.
"""

from __future__ import annotations

from typing import Any, Dict, List

from app.modules.residence_permits.domain.interfaces import IResidencePermitListReader
from app.modules.residence_permits.infrastructure.queries import (
    fetch_employees_for_residence_permits_list,
)


class ResidencePermitListRepository(IResidencePermitListReader):
    """Lit la liste des employés soumis au titre de séjour pour une company."""

    def get_employees_subject_for_company(
        self, company_id: str
    ) -> List[Dict[str, Any]]:
        return fetch_employees_for_residence_permits_list(company_id)
