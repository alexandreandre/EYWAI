"""
Repository residence_permits : implémentation des ports de lecture.

Délègue aux queries infrastructure. Aucune entité persistée dans ce module.
"""

from __future__ import annotations

from typing import Any, Dict, List

from app.modules.residence_permits.domain.interfaces import (
    IResidencePermitExportReader,
    IResidencePermitListReader,
)
from app.modules.residence_permits.infrastructure.queries import (
    fetch_employees_for_residence_permits_export,
    fetch_employees_for_residence_permits_list,
)


class ResidencePermitListRepository(
    IResidencePermitListReader, IResidencePermitExportReader
):
    """Lit les employés soumis au titre de séjour, en liste ou pour l'export."""

    def get_employees_subject_for_company(
        self, company_id: str
    ) -> List[Dict[str, Any]]:
        return fetch_employees_for_residence_permits_list(company_id)

    def get_employees_for_export(
        self, company_id: str, employee_ids: List[str]
    ) -> List[Dict[str, Any]]:
        return fetch_employees_for_residence_permits_export(company_id, employee_ids)
