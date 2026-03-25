"""
Schéma partagé pour les réponses contenant une URL signée (contrat, document, etc.).
Utilisé par employees, payslip et autres modules.
"""

from pydantic import BaseModel


class ContractResponse(BaseModel):
    """Réponse avec URL signée de téléchargement (ou None si absent)."""

    url: str | None = None
