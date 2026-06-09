"""
Schéma partagé pour les réponses contenant une URL signée (contrat, document, etc.).
Utilisé par employees, payslip et autres modules.
"""

from pydantic import BaseModel


class ContractResponse(BaseModel):
    """Réponse avec URLs signées (téléchargement et aperçu inline)."""

    url: str | None = None
    preview_url: str | None = None
