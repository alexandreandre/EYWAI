"""
Schémas Pydantic entrée API du module schedules.

Définitions canoniques : calendrier prévu/réel, apply-model.
Comportement identique à l’ancien schemas/schedule.py et api/routers/schedules.py.
"""

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


# ----- Calendrier prévu (GET/POST /planned-calendar) -----


class PlannedCalendarEntry(BaseModel):
    """
    Entrée du calendrier prévu pour un jour.

    Note sur heures_prevues :
    - Pour forfait jour : 1 = jour travaillé, 0/null = jour non travaillé
    - Pour non forfait jour : nombre d'heures (ex: 8, 7.5)
    Le forfait jour est déterminé par employees.statut (contient "forfait jour").
    """

    # Les métadonnées d'absence (arret_type, subrogation_active,
    # nombre_enfants, historique_arrets_annee, date_debut_arret_reel…) ne
    # figurent PAS ici : elles sont propriété du serveur
    # (`app.shared.domain.absence_calendar.SERVER_OWNED_ABSENCE_KEYS`) et sont
    # reprises depuis l'entrée stockée par `merge_planned_entries`. Les
    # accepter en entrée laisserait « copier le mois précédent » rejouer un
    # arrêt de travail sur un mois qui n'en a pas.
    jour: int = Field(ge=1, le=31)
    type: str
    heures_prevues: float | None = None


class PlannedCalendarRequest(BaseModel):
    year: int
    month: int
    calendrier_prevu: List[PlannedCalendarEntry]


# ----- Heures réelles (GET/POST /actual-hours) -----


class ActualHoursEntry(BaseModel):
    jour: int
    heures_faites: float | None = None
    type: str | None = None


class ActualHoursRequest(BaseModel):
    year: int
    month: int
    calendrier_reel: List[ActualHoursEntry]


class ImportBadgeuseEmployeeRequest(BaseModel):
    year: int
    month: int
    recalculate_payroll: bool = False


class ImportBadgeuseBulkRequest(BaseModel):
    company_id: str
    employee_ids: List[str]
    year: int
    month: int
    recalculate_payroll: bool = False


# ----- Apply-model (POST /api/schedules/apply-model) -----


class DayConfigModel(BaseModel):
    """Configuration d'un jour pour apply-model (work, rest, holiday, etc.)."""

    type: Literal[
        "work",
        "rest",
        "holiday",
        "travail",
        "weekend",
        "conge",
        "ferie",
        "arret_maladie",
    ]
    hours: float


class WeekConfigModel(BaseModel):
    """Configuration d'une semaine (lundi à dimanche)."""

    monday: DayConfigModel
    tuesday: DayConfigModel
    wednesday: DayConfigModel
    thursday: DayConfigModel
    friday: DayConfigModel
    saturday: DayConfigModel
    sunday: DayConfigModel


class ApplyModelRequest(BaseModel):
    """Body POST /api/schedules/apply-model : appliquer un modèle à plusieurs employés."""

    employee_ids: List[str]
    year: int
    month: int
    week_configs: Dict[
        int, WeekConfigModel
    ]  # 1-5 : configuration de chaque semaine du mois


# ----- Plans de calendriers horaires (POST/PUT /api/schedules/plans) -----


class SchedulePlanUpsert(BaseModel):
    """Création/mise à jour d'un plan d'affectation de calendrier."""

    name: str
    scope_type: Literal["company", "team", "service", "employees"] = "company"
    scope_ref: Dict[str, Any] = Field(default_factory=dict)
    template_cycle: List[str] = Field(default_factory=list)  # cycle ordonné (alternance)
    cycle_anchor: Optional[str] = None
    start_date: str
    end_date: Optional[str] = None
    overwrite_mode: Literal["overwrite_all", "preserve_manual", "fill_empty"] = (
        "preserve_manual"
    )
    needs_confirmation: bool = False
    notes: Optional[str] = None
    is_active: bool = True


class ApplyPresetRequest(BaseModel):
    preset_key: str


class GenerateCalendarRequest(BaseModel):
    """Lance la génération d'un plan (ou plan inline) sur une année/plage."""

    plan_id: Optional[str] = None
    year: Optional[int] = None
    overwrite_mode: Optional[
        Literal["overwrite_all", "preserve_manual", "fill_empty"]
    ] = None
    dry_run: bool = True
    recalculate_payroll: bool = False


__all__ = [
    "ActualHoursEntry",
    "ActualHoursRequest",
    "ImportBadgeuseBulkRequest",
    "ImportBadgeuseEmployeeRequest",
    "ApplyModelRequest",
    "ApplyPresetRequest",
    "DayConfigModel",
    "GenerateCalendarRequest",
    "PlannedCalendarEntry",
    "PlannedCalendarRequest",
    "SchedulePlanUpsert",
    "WeekConfigModel",
]
