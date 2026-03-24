"""
Commandes applicatives : documents de sortie (certificat de travail, attestation Pôle Emploi, solde de tout compte).
employee_exits et compat appellent ce module ; le générateur concret est dans solde_de_tout_compte.
"""

from __future__ import annotations

from typing import Any, Dict

from app.modules.payroll.solde_de_tout_compte import EmployeeExitDocumentGenerator


def get_exit_document_generator() -> Any:
    """Retourne une instance du générateur de documents de sortie (solde_de_tout_compte)."""
    return EmployeeExitDocumentGenerator()
