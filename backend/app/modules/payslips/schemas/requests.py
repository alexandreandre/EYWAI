"""
Schémas de requête du module payslips.

Structure alignée sur schemas.payslip (legacy). Migration : remplacer les usages
par ces schémas puis retirer l'ancien fichier.
"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.payroll.engine.corrections_manuelles import (
    CorrectionDeLigne,
    CorrectionInvalide,
    RegularisationCotisation,
    RegularisationInvalide,
)
from app.modules.payslips.domain.corrections import CorrectionsBulletin
from app.modules.payslips.domain.primes_editees import DiffPrimes


class PayslipRequest(BaseModel):
    """Requête de génération d'un bulletin (employee_id, year, month).

    Les overrides sont explicites et jamais le défaut :
    - force_calendrier_incomplet : générer malgré un calendrier `a_saisir` (422 sinon).
    - regenerer_bulletin_valide : écraser un bulletin validé, avec archivage (409 sinon).
    - partir_de_cumuls_a_zero : reprise non posée, générer en partant de cumuls à
      zéro (422 `reprise_non_posee` sinon) ; le bulletin garde qui et quand.
    """

    employee_id: str
    year: int
    month: int
    force_calendrier_incomplet: bool = False
    regenerer_bulletin_valide: bool = False
    partir_de_cumuls_a_zero: bool = False


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
    #: Retenue ou versement sur le net à payer, sans toucher au brut (acompte,
    #: avance…) : le montant porte alors son signe.
    sur_le_net: bool = False
    catalog_prime_id: str | None = Field(None, max_length=120)


class PrimeCorrigee(BaseModel):
    """Le nouveau montant d'une prime saisie du mois."""

    model_config = ConfigDict(extra="forbid")

    saisie_id: str = Field(..., min_length=1, max_length=64)
    amount: float = Field(..., ge=-100_000, le=100_000)


class RegularisationAjoutee(BaseModel):
    """Une régularisation de cotisation saisie depuis le bulletin.

    Le serveur calcule les montants d'une régularisation par la base. Il ne
    reçoit un montant que pour une cotisation sans taux.
    """

    model_config = ConfigDict(extra="forbid")

    coti_id: str = Field(..., min_length=1, max_length=80)
    libelle: str = Field(..., min_length=1, max_length=160)
    motif: str = Field(..., min_length=3, max_length=300)
    base: float | None = Field(None, ge=-1_000_000, le=1_000_000)
    taux_salarial: float | None = Field(None, ge=-1, le=1)
    taux_patronal: float | None = Field(None, ge=-1, le=1)
    montant_salarial: float | None = Field(None, ge=-100_000, le=100_000)
    montant_patronal: float | None = Field(None, ge=-100_000, le=100_000)

    @model_validator(mode="after")
    def _regularisation_coherente(self) -> "RegularisationAjoutee":
        try:
            self.vers_domaine()
        except RegularisationInvalide as exc:
            raise ValueError(str(exc)) from exc
        return self

    def vers_domaine(self) -> RegularisationCotisation:
        return RegularisationCotisation(**self.model_dump())


class CorrectionLigneAjoutee(BaseModel):
    """Une ligne corrigée depuis le bulletin : sa base, son taux ou son montant,
    selon ce que la ligne porte (règle 3). Le serveur calcule le montant."""

    model_config = ConfigDict(extra="forbid")

    ligne: str = Field(..., min_length=1, max_length=200)
    libelle: str = Field(..., min_length=1, max_length=160)
    motif: str = Field(..., min_length=3, max_length=300)
    base: float | None = Field(None, ge=-1_000_000, le=1_000_000)
    taux: float | None = Field(None, ge=-1_000, le=1_000)
    montant: float | None = Field(None, ge=-1_000_000, le=1_000_000)
    taux_salarial: float | None = Field(None, ge=-1, le=1)
    taux_patronal: float | None = Field(None, ge=-1, le=1)
    montant_salarial: float | None = Field(None, ge=-100_000, le=100_000)
    montant_patronal: float | None = Field(None, ge=-100_000, le=100_000)

    @model_validator(mode="after")
    def _correction_coherente(self) -> "CorrectionLigneAjoutee":
        try:
            self.vers_domaine()
        except CorrectionInvalide as exc:
            raise ValueError(str(exc)) from exc
        return self

    def vers_domaine(self) -> CorrectionDeLigne:
        return CorrectionDeLigne(**self.model_dump())


class CorrectionsBulletinRequest(BaseModel):
    """Ce qui se corrige depuis le bulletin : heures sup, primes et régularisations de cotisation du mois."""

    model_config = ConfigDict(extra="forbid")

    heures_sup: HeuresSupCorrigees | None = None
    revenir_au_planning: bool = False
    primes_ajoutees: list[PrimeAjoutee] = Field(default_factory=list, max_length=20)
    primes_corrigees: list[PrimeCorrigee] = Field(default_factory=list, max_length=50)
    primes_retirees: list[str] = Field(default_factory=list, max_length=50)
    regularisations_ajoutees: list[RegularisationAjoutee] = Field(default_factory=list, max_length=20)
    regularisations_retirees: list[str] = Field(default_factory=list, max_length=50)
    corrections_ajoutees: list[CorrectionLigneAjoutee] = Field(default_factory=list, max_length=20)
    corrections_retirees: list[str] = Field(default_factory=list, max_length=50)

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
            regularisations_ajoutees=tuple(r.vers_domaine() for r in self.regularisations_ajoutees),
            regularisations_retirees=tuple(dict.fromkeys(self.regularisations_retirees)),
            corrections_ajoutees=tuple(c.vers_domaine() for c in self.corrections_ajoutees),
            corrections_retirees=tuple(dict.fromkeys(self.corrections_retirees)),
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


class ValidationGroupeeRequest(BaseModel):
    """Les bulletins prêts du mois à valider en une fois."""

    payslip_ids: list[str] = Field(..., min_length=1, max_length=500)


class ReportNetNegatifActionRequest(BaseModel):
    """Création, mise à jour ou suppression du report d'un net négatif."""

    action: Literal["creer", "mettre_a_jour", "supprimer"]


class PayslipPreviewRequest(BaseModel):
    """Aperçu du bulletin enregistré, avec la note du PDF en cours de saisie.

    Le bulletin n'est plus envoyé par l'écran : l'aperçu montre ce qui est
    enregistré, seule la note peut différer.
    """

    model_config = ConfigDict(extra="forbid")

    pdf_notes: str | None = Field(
        None, max_length=2000, description="Note visible sur le bulletin"
    )
