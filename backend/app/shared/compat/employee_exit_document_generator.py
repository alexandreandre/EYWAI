"""
Wrapper de compatibilité : générateur de documents de sortie.

Délègue à app.modules.payroll.solde_de_tout_compte (source de vérité).
Utilisé par app.modules.employee_exits pour obtenir une implémentation de
IExitDocumentGenerator.
"""

from typing import Any, Dict

from app.modules.employee_exits.domain.interfaces import IExitDocumentGenerator


def get_employee_exit_document_generator() -> IExitDocumentGenerator:
    """
    Retourne une implémentation de IExitDocumentGenerator.
    Source : app.modules.payroll.solde_de_tout_compte.EmployeeExitDocumentGenerator.
    """
    from app.modules.payroll.solde_de_tout_compte import EmployeeExitDocumentGenerator

    return _ExitDocumentGeneratorAdapter(EmployeeExitDocumentGenerator())


class _ExitDocumentGeneratorAdapter(IExitDocumentGenerator):
    """Adapte EmployeeExitDocumentGenerator (legacy) vers IExitDocumentGenerator."""

    def __init__(self, generator: Any):
        self._generator = generator

    def generate_certificat_travail(
        self,
        employee_data: Dict[str, Any],
        company_data: Dict[str, Any],
        exit_data: Dict[str, Any],
    ) -> bytes:
        return self._generator.generate_certificat_travail(
            employee_data, company_data, exit_data
        )

    def generate_attestation_pole_emploi(
        self,
        employee_data: Dict[str, Any],
        company_data: Dict[str, Any],
        exit_data: Dict[str, Any],
    ) -> bytes:
        return self._generator.generate_attestation_pole_emploi(
            employee_data, company_data, exit_data
        )

    def generate_solde_tout_compte(
        self,
        employee_data: Dict[str, Any],
        company_data: Dict[str, Any],
        exit_data: Dict[str, Any],
        indemnities: Dict[str, Any],
        supabase_client: Any = None,
    ) -> bytes:
        return self._generator.generate_solde_tout_compte(
            employee_data, company_data, exit_data, indemnities, supabase_client
        )
