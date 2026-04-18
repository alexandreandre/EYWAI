"""
Schémas de réponse du module payslips.

Structure alignée sur schemas.payslip (legacy). Migration : remplacer les usages
par ces schémas puis retirer l'ancien fichier.
"""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel


class PayslipInfo(BaseModel):
    """Ligne de liste de bulletins (moi, employé, etc.)."""

    id: str
    name: str
    month: int
    year: int
    url: str
    net_a_payer: float | None = None
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
    edited_by: str
    edited_by_name: str
    changes_summary: str
    previous_payslip_data: dict[str, Any]
    previous_pdf_url: str | None = None


class PayslipDetail(BaseModel):
    """Détail complet d'un bulletin (dont payslip_data, cumuls, historique)."""

    id: str
    employee_id: str
    company_id: str
    name: str
    month: int
    year: int
    url: str
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
    new_pdf_url: str


class PayslipRestoreResponse(BaseModel):
    """Réponse après restauration d'une version."""

    status: str
    message: str
    payslip: PayslipDetail
    restored_version: int
