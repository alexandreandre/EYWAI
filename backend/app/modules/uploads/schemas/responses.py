"""
Schémas de réponse pour le module uploads.

Contrat API sortie strictement identique à api/routers/uploads.py.
"""

from pydantic import BaseModel, Field


class UploadLogoResponse(BaseModel):
    """Réponse POST /logo. Champs exacts du legacy."""

    success: bool = True
    logo_url: str = Field(..., description="URL publique du logo")
    message: str = Field(
        default="Logo uploadé avec succès",
        description="Message retourné par le legacy",
    )


class DeleteLogoResponse(BaseModel):
    """
    Réponse DELETE /logo/{entity_type}/{entity_id}.
    message vaut soit "Logo supprimé avec succès", soit "Aucun logo à supprimer".
    """

    success: bool = True
    message: str = Field(
        ...,
        description="'Logo supprimé avec succès' ou 'Aucun logo à supprimer'",
    )


class LogoScaleResponse(BaseModel):
    """Réponse PATCH /logo-scale/{entity_type}/{entity_id}. Champs exacts du legacy."""

    success: bool = True
    logo_scale: float = Field(..., description="Facteur de zoom mis à jour")
    message: str = Field(
        default="Facteur de zoom mis à jour avec succès",
        description="Message retourné par le legacy",
    )


class BdesUploadResponse(BaseModel):
    """Réponse POST /bdes : chemin storage pour enchaînement CSE."""

    path: str = Field(..., description="Chemin du fichier dans le bucket")
