"""
Schémas de réponse du module payslips.

Structure alignée sur schemas.payslip (legacy). Migration : remplacer les usages
par ces schémas puis retirer l'ancien fichier.
"""

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel


class PayslipInfo(BaseModel):
    """Ligne de liste de bulletins (moi, employé, etc.)."""

    id: str
    name: str
    month: int
    year: int
    url: str
    preview_url: str = ""
    net_a_payer: float | None = None
    warnings: list[str] = []
    #: Points à arbitrer par la RH (plafond transport…) : pas des alertes.
    points_a_arbitrer: list[str] = []
    #: « importe » : bulletin repris de l'ancien logiciel, intouchable.
    origine: str = "calcule"
    #: true = une donnée du bulletin a changé depuis le calcul ; false = à jour ;
    #: null = bulletin d'avant l'empreinte, repris ou d'un ancien contrat.
    a_recalculer: bool | None = None
    #: Ce qui a changé, dit simplement (« La mutuelle a changé… ») ; None si rien.
    raison_a_recalculer: str | None = None
    salaire_brut: float | None = None
    heures_sup: float | None = None
    #: « valide » ou « brouillon » ; la paie du mois montre « Validé » sur la ligne.
    status: str | None = None
    manually_edited: bool = False
    edit_count: int = 0
    edited_at: datetime | None = None
    edited_by: str | None = None


class InternalNote(BaseModel):
    """Note interne sur un bulletin."""

    id: str
    author_id: str
    author_name: str
    timestamp: datetime
    content: str


class HistoryEntry(BaseModel):
    """Entrée d'historique d'édition d'un bulletin."""

    version: int
    edited_at: datetime
    # Absents quand la version a été archivée par une régénération sans
    # utilisateur connu (script, backtest) : l'écran affiche « Système ».
    edited_by: str | None = None
    edited_by_name: str | None = None
    changes_summary: str
    previous_payslip_data: dict[str, Any]
    #: Lien vers le PDF de cette version (signé à la lecture quand le PDF est gardé).
    previous_pdf_url: str | None = None
    pdf_storage_path: str | None = None


class ExportDuMois(BaseModel):
    """Un export déjà fait pour le mois du bulletin."""

    type: str
    libelle: str
    date: str
    #: Un bulletin du mois a été recalculé, supprimé ou ajouté depuis : à refaire.
    a_refaire: bool = False


class PayslipDetail(BaseModel):
    """Détail complet d'un bulletin (dont payslip_data, cumuls, historique)."""

    id: str
    employee_id: str
    company_id: str
    name: str
    month: int
    year: int
    url: str
    preview_url: str = ""
    pdf_storage_path: str
    payslip_data: dict[str, Any]
    manually_edited: bool = False
    edit_count: int = 0
    edited_at: datetime | None = None
    edited_by: str | None = None
    internal_notes: list[InternalNote] = []
    pdf_notes: str | None = None
    edit_history: list[HistoryEntry] = []
    cumuls: dict[str, Any] | None = None
    status: str = "brouillon"
    validated_at: datetime | None = None
    validated_by: str | None = None
    #: Dernière mise à jour : l'écran la renvoie avec une correction, qui est
    #: refusée si le bulletin a changé entre-temps.
    updated_at: datetime | None = None
    period_edit_locked: bool = False
    manual_edit_locked: bool = False
    manual_edit_lock_reason: str | None = None
    manual_edit_lock_until: date | None = None
    #: Phrase à afficher quand le mois précédent a changé depuis le calcul de
    #: ce bulletin (cumuls qui ne se suivent plus) ; None sinon.
    a_regenerer: str | None = None
    #: true = à recalculer ; false = à jour ; null = inconnu (pas d'empreinte).
    a_recalculer: bool | None = None
    #: Ce qui a changé dans ses entrées (« La mutuelle a changé… ») ; None si
    #: rien — le mois d'avant se dit par `a_regenerer`.
    raison_a_recalculer: str | None = None
    #: Brut, net, heures sup et absences vs le bulletin du mois précédent.
    comparaison_mois_dernier: dict[str, Any] | None = None
    #: Exports déjà faits pour le mois (type, libellé, date) : à refaire après
    #: une correction. Vide pour le salarié.
    exports_du_mois: list[ExportDuMois] = []


AlertLevelResponse = Literal["CRITIQUE", "AVERTISSEMENT", "INFO"]


class PayslipAlertResponse(BaseModel):
    """Alerte de comparaison ou de tendance."""

    rule_id: str
    level: AlertLevelResponse
    message: str
    field: str
    value_n: float
    value_n1: float
    delta_pct: float
    status: str = "active"
    acquitted_by: str | None = None
    acquitted_at: str | None = None
    comment: str | None = None


class ComparisonLineResponse(BaseModel):
    """Ligne de comparaison d'agrégats."""

    libelle: str
    value_n: float | None = None
    value_n1: float | None = None
    delta_abs: float | None = None
    delta_pct: float | None = None
    alert_level: AlertLevelResponse | None = None


class ComparisonResultResponse(BaseModel):
    """Résultat complet comparaison N vs N-1."""

    bulletin_n_id: str
    bulletin_n1_id: str | None = None
    month_n: int
    year_n: int
    month_n1: int | None = None
    year_n1: int | None = None
    lines: list[ComparisonLineResponse]
    alerts: list[PayslipAlertResponse]
    has_critical: bool


class TrendMonthResponse(BaseModel):
    """Point mensuel pour la tendance."""

    month: int
    year: int
    payslip_id: str
    salaire_brut: float
    net_a_payer: float
    total_cotisations: float
    alerts: list[PayslipAlertResponse]


class TrendResponse(BaseModel):
    """Tendance sur les bulletins validés précédents."""

    employee_id: str
    months: list[TrendMonthResponse]


class PayslipEditResponse(BaseModel):
    """Réponse après édition d'un bulletin."""

    status: str
    message: str
    payslip: PayslipDetail
    new_pdf_url: str | None = None
    #: Vrai quand le moteur a recalculé le bulletin après les corrections.
    recalcule: bool = False
    #: Présent si le moteur n'a pas pu recalculer : les variables du mois sont
    #: écrites, le bulletin est marqué « recalcul en attente ». Sans cette
    #: déclaration, FastAPI retirerait le champ.
    recalcul_erreur: str | None = None
    #: Le refus structuré du recalcul (`{code, message, **details}`, le même
    #: que la génération rend en HTTP), pour que l'écran propose la sortie :
    #: « effacer ces heures » pour `heures_sur_jour_d_arret`, par exemple.
    recalcul_refus: dict[str, Any] | None = None


class PayslipRestoreResponse(BaseModel):
    """Réponse après restauration d'une version."""

    status: str
    message: str
    payslip: PayslipDetail
    restored_version: int
    recalcule: bool = False
    recalcul_erreur: str | None = None
    recalcul_refus: dict[str, Any] | None = None


class RefusDeValidation(BaseModel):
    """Un bulletin non validé par la validation groupée, et pourquoi."""

    payslip_id: str
    raison: str


class ValidationGroupeeResponse(BaseModel):
    """Ce que la validation groupée a validé, et ce qu'elle a refusé."""

    valides: list[str]
    refus: list[RefusDeValidation]


class PayslipPreviewResponse(BaseModel):
    """Bulletin rendu, prêt à être affiché tel quel."""

    html: str
