"""
Schémas de requête du module residence_permits.
"""

from typing import List

from pydantic import BaseModel, Field


class ResidencePermitExportRequest(BaseModel):
    """
    Salariés à exporter, désignés par le navigateur.

    Ce sont les lignes affichées à l'écran, dans leur ordre d'affichage. Les
    identifiants désignent, ils n'autorisent pas : le serveur borne la lecture à
    l'entreprise active.
    """

    employee_ids: List[str] = Field(
        ..., description="Identifiants des salariés affichés, dans l'ordre de l'écran"
    )
