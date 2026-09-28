"""
Schémas de requête du module payslips.

Structure alignée sur schemas.payslip (legacy). Migration : remplacer les usages
par ces schémas puis retirer l'ancien fichier.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.payslips.domain.corrections import CorrectionsBulletin
from app.modules.payslips.domain.primes_editees import DiffPrimes


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


class HeuresSupCorrigees(BaseModel):
    """Heures sup du mois déclarées depuis le bulletin, par palier."""

    model_config = ConfigDict(extra="forbid")

    hs25: float = Field(..., ge=0, le=300)
    hs50: float = Field(..., ge=0, le=300)


class PrimeAjoutee(BaseModel):
    """Une prime du mois ajoutée depuis le bulletin."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=120)
    amount: float = Field(..., ge=-100_000, le=100_000)
    is_socially_taxed: bool = True
    is_taxable: bool = True
    catalog_prime_id: str | None = Field(None, max_length=120)


class PrimeCorrigee(BaseModel):
    """Le nouveau montant d'une prime saisie du mois."""

    model_config = ConfigDict(extra="forbid")

    saisie_id: str = Field(..., min_length=1, max_length=64)
    amount: float = Field(..., ge=-100_000, le=100_000)


class CorrectionsBulletinRequest(BaseModel):
    """Ce qui se corrige depuis le bulletin : heures sup et primes du mois."""

    model_config = ConfigDict(extra="forbid")

    heures_sup: HeuresSupCorrigees | None = None
    revenir_au_planning: bool = False
    primes_ajoutees: list[PrimeAjoutee] = Field(default_factory=list, max_length=20)
    primes_corrigees: list[PrimeCorrigee] = Field(default_factory=list, max_length=50)
    primes_retirees: list[str] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def _pas_deux_consignes_contraires(self) -> "CorrectionsBulletinRequest":
        if self.heures_sup is not None and self.revenir_au_planning:
            raise ValueError(
                "Choisissez entre déclarer les heures sup et revenir au planning."
            )
        corrigees = {p.saisie_id for p in self.primes_corrigees}
        if corrigees & set(self.primes_retirees):
            raise ValueError("Une même prime ne peut pas être corrigée et retirée.")
        return self

    def vers_domaine(self) -> CorrectionsBulletin:
        return CorrectionsBulletin(
            heures_sup=(
                (self.heures_sup.hs25, self.heures_sup.hs50)
                if self.heures_sup is not None
                else None
            ),
            revenir_au_planning=self.revenir_au_planning,
            primes=DiffPrimes(
                ajoutees=tuple(
                    {**p.model_dump(), "amount": round(p.amount, 2)}
                    for p in self.primes_ajoutees
                ),
                modifiees=tuple(
                    (p.saisie_id, round(p.amount, 2)) for p in self.primes_corrigees
                ),
                retirees=tuple(dict.fromkeys(self.primes_retirees)),
            ),
        )


class PayslipEditRequest(BaseModel):
    """Correction d'un bulletin : ses variables du mois et ses notes.

    Le bulletin lui-même n'est plus envoyé : il est recalculé par le moteur à
    partir des variables corrigées (audit du 28/09).
    """

    model_config = ConfigDict(extra="forbid")

    corrections: CorrectionsBulletinRequest = Field(
        default_factory=CorrectionsBulletinRequest
    )
    changes_summary: str | None = Field(
        None, max_length=500, description="Résumé des modifications effectuées"
    )
    pdf_notes: str | None = Field(
        None,
        max_length=2000,
        description="Note visible sur le PDF (absente : inchangée ; vide : effacée)",
    )
    internal_note: str | None = Field(
        None, max_length=1000, description="Note interne (non visible sur le PDF)"
    )
    base_updated_at: str | None = Field(
        None,
        max_length=64,
        description="Date de mise à jour du bulletin lu par l'écran (conflit sinon)",
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
