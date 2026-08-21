"""
Schémas de requête du module payslips.

Structure alignée sur schemas.payslip (legacy). Migration : remplacer les usages
par ces schémas puis retirer l'ancien fichier.
"""

from typing import Any

from pydantic import BaseModel, Field


class PayslipRequest(BaseModel):
    """Requête de génération d'un bulletin (employee_id, year, month).

    Les overrides sont explicites et jamais le défaut :
    - force_calendrier_incomplet : générer malgré un calendrier `a_saisir` (422 sinon).
    - regenerer_bulletin_valide : écraser un bulletin validé, avec archivage (409 sinon).
    """

    employee_id: str
    year: int
    month: int
    force_calendrier_incomplet: bool = False
    regenerer_bulletin_valide: bool = False


class PayslipEditRequest(BaseModel):
    """Requête d'édition d'un bulletin existant."""

    payslip_data: dict[str, Any]
    changes_summary: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Résumé des modifications effectuées",
    )
    pdf_notes: str | None = Field(
        None, max_length=2000, description="Notes visibles sur le PDF"
    )
    internal_note: str | None = Field(
        None, max_length=1000, description="Note interne (non visible sur le PDF)"
    )


class PayslipRestoreRequest(BaseModel):
    """Requête de restauration d'une version d'un bulletin."""

    version: int = Field(..., ge=1, description="Numéro de version à restaurer")


class InternalNoteCreate(BaseModel):
    """Création d'une note interne sur un bulletin."""

    content: str


class AcquitAlertRequest(BaseModel):
    """Acquittement ou commentaire sur une alerte."""

    comment: str | None = None


class PayslipPreviewRequest(BaseModel):
    """Rendu d'aperçu d'un bulletin à partir de données éditées, sans persistance."""

    payslip_data: dict[str, Any]
    pdf_notes: str | None = Field(
        None, max_length=2000, description="Notes visibles sur le bulletin"
    )
