"""
Schémas Pydantic pour la saisie assistée du calendrier (page Calendriers RH).

Deux entrées possibles produisent la même proposition (non persistée) :
- instruction en langage naturel (texte / dictée vocale transcrite côté client) ;
- relevé de pointeuse (PDF / image) analysé par OCR + LLM.

Chaque jour proposé porte une `nature` : « prevu » (heures prévues, planning
prévisionnel) ou « reel » (heures faites, réalisées). La proposition est ensuite
revue par le RH dans le front, qui persiste vers le calendrier prévu
(POST /planned-calendar) et/ou les heures réelles (POST /actual-hours).
"""

from datetime import date
from typing import List, Literal, Optional

from pydantic import BaseModel, Field

TimesheetScope = Literal["weekly", "monthly", "unknown"]
TimesheetConfidence = Literal["high", "medium", "low"]
DocumentScopeInput = Literal["auto", "weekly", "monthly"]
ReviewStatus = Literal["ok", "warning", "error", "empty"]
MatchMethod = Literal["matricule", "name_exact", "name_fuzzy", "none"]
QualityLevel = Literal["ok", "warning", "error", "info"]

DayNature = Literal["prevu", "reel"]


class RosterEmployee(BaseModel):
    """Employé candidat fourni par le front pour la résolution nom -> id."""

    id: str
    first_name: str
    last_name: str
    time_tracking_id: Optional[str] = None


class ParseInstructionRequest(BaseModel):
    """Body POST /api/schedules/assisted-fill/parse-text."""

    year: int
    month: int
    instruction: str = Field(..., min_length=1)
    employees: List[RosterEmployee] = Field(default_factory=list)
    single_employee: bool = False
    broadcast: bool = False


class AiDayEntry(BaseModel):
    """Une journée proposée par l'IA pour un employé."""

    jour: int
    heures: Optional[float] = None
    type: str = "travail"
    nature: DayNature = "reel"
    punch_entry_raw: Optional[str] = None
    punch_exit_raw: Optional[str] = None
    shift_code: Optional[str] = None
    planned_paid_break_minutes: Optional[int] = None
    # Mois/année réels du jour si différents du (year, month) de la proposition
    # (semaine hebdomadaire à cheval sur deux mois). None = utiliser le mois de
    # la proposition, pour compatibilité avec les imports non ancrés.
    year: Optional[int] = None
    month: Optional[int] = None


class TimesheetQualityCheck(BaseModel):
    """Contrôle qualité automatique (total hebdo, match, couverture…)."""

    level: QualityLevel
    code: str
    message: str
    employee_raw_name: Optional[str] = None
    matricule: Optional[str] = None


class AffectedMonth(BaseModel):
    """Mois touché par un relevé (semaine à cheval sur 2 mois)."""

    year: int
    month: int
    days: List[int] = Field(default_factory=list)


class AiEmployeeProposal(BaseModel):
    """Proposition pour un employé : résolution + jours détectés."""

    raw_name: str
    employee_id: Optional[str] = None
    matched_name: Optional[str] = None
    match_confidence: Literal["high", "medium", "none"] = "none"
    match_method: MatchMethod = "none"
    time_tracking_id: Optional[str] = None
    review_status: ReviewStatus = "ok"
    days: List[AiDayEntry] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    weekly_total_pdf: Optional[float] = None
    weekly_total_imported: Optional[float] = None
    weekly_total_gap: Optional[float] = None
    days_expected_count: Optional[int] = None
    days_imported_count: Optional[int] = None
    coverage_ratio: Optional[float] = None
    quality_issue: Optional[str] = None


class AiCalendarProposalResponse(BaseModel):
    """Proposition complète renvoyée au front (jamais écrite directement)."""

    year: int
    month: int
    source: str
    employees: List[AiEmployeeProposal] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    detected_scope: TimesheetScope = "unknown"
    detected_period_start: Optional[date] = None
    detected_period_end: Optional[date] = None
    period_confidence: TimesheetConfidence = "low"
    period_warnings: List[str] = Field(default_factory=list)
    detected_days_count: int = 0
    suggested_year: Optional[int] = None
    suggested_month: Optional[int] = None
    month_auto_corrected: bool = False
    requested_year: Optional[int] = None
    requested_month: Optional[int] = None
    month_correction_message: Optional[str] = None
    quality_checks: List[TimesheetQualityCheck] = Field(default_factory=list)
    detected_format: Optional[str] = None
    parse_confidence: Optional[float] = None
    focus_week_index: Optional[int] = None
    affected_months: List[AffectedMonth] = Field(default_factory=list)
    roster_not_in_document_count: int = 0
    review_summary: Optional[dict] = None
    extraction_method: Optional[str] = None
    extraction_warnings: List[str] = Field(default_factory=list)
    extraction_pages_total: Optional[int] = None
    extraction_pages_processed: Optional[int] = None
    extraction_truncated: bool = False
    extraction_mode: Optional[str] = None
    consensus_conflicts: Optional[int] = None


class TimesheetExtractStartResponse(BaseModel):
    job_id: str
    status: Literal["queued", "extracting"]


class TimesheetExtractProgress(BaseModel):
    phase: str = "queued"
    pages_total: int = 0
    pages_done: int = 0
    current_page: int = 0
    batch_id: Optional[str] = None
    files_total: Optional[int] = None
    files_done: Optional[int] = None


class TimesheetExtractJobResponse(BaseModel):
    job_id: str
    status: Literal["queued", "extracting", "completed", "failed", "cancelled"]
    progress: TimesheetExtractProgress = Field(default_factory=TimesheetExtractProgress)
    proposal: Optional[AiCalendarProposalResponse] = None
    error_message: Optional[str] = None
    extraction_warnings: List[str] = Field(default_factory=list)


__all__ = [
    "AffectedMonth",
    "AiCalendarProposalResponse",
    "AiDayEntry",
    "AiEmployeeProposal",
    "DayNature",
    "DocumentScopeInput",
    "MatchMethod",
    "ParseInstructionRequest",
    "QualityLevel",
    "ReviewStatus",
    "RosterEmployee",
    "TimesheetConfidence",
    "TimesheetExtractJobResponse",
    "TimesheetExtractProgress",
    "TimesheetExtractStartResponse",
    "TimesheetQualityCheck",
    "TimesheetScope",
]
