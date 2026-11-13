"""
Schémas Pydantic entrée API du module schedules.

Définitions canoniques : calendrier prévu/réel, apply-model.
Comportement identique à l’ancien schemas/schedule.py et api/routers/schedules.py.
"""

from typing import Any, Dict, List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator


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
    # Demi-journée choisie au calendrier pour un jour CP/RTT nouvellement
    # saisi : elle part avec la demande créée (0,5 jour), jamais écrite telle
    # quelle au planning (clé serveur, posée par la projection de la demande).
    # Hors `model_dump()` : lue par `update_planned_calendar` seulement.
    # Tolérante : un jour relu du serveur la renvoie ; seules « matin » et
    # « apres_midi » sont retenues, le reste est ignoré.
    demi_journee: str | None = Field(default=None, exclude=True)


class PlannedCalendarRequest(BaseModel):
    year: int
    month: int
    calendrier_prevu: List[PlannedCalendarEntry]
    expected_revision: UUID | None = None


class PlannedCalendarEntryOut(BaseModel):
    """Entrée telle que stockée — lecture tolérante.

    Les bornes de saisie (jour 1-31) ne s'appliquent pas à la lecture : une
    donnée historique hors bornes doit rester lisible (et corrigeable), pas
    transformer le GET en 500.
    """

    jour: int
    type: str | None = None
    heures_prevues: float | None = None
    # Marqueur de provenance, exposé en LECTURE seulement : le client s'en
    # sert pour exclure les jours d'absence validée de ses actions de masse
    # (copie de mois, modèle de semaine). Toujours refusé en écriture
    # (PlannedCalendarEntry + SERVER_OWNED_ABSENCE_KEYS).
    origine: str | None = None
    # Demi-journée de CP, LECTURE seulement (mêmes règles que `origine`) :
    # quotite_absence=0.5 + demi_journee "matin"/"apres_midi" pour l'affichage.
    quotite_absence: float | None = None
    demi_journee: str | None = None


class PlannedCalendarResponse(BaseModel):
    year: int
    month: int
    calendrier_prevu: List[PlannedCalendarEntryOut]


# ----- Heures réelles (GET/POST /actual-hours) -----


class ActualHoursEntry(BaseModel):
    jour: int
    heures_faites: float | None = None
    type: str | None = None


class ActualHoursRequest(BaseModel):
    year: int
    month: int
    calendrier_reel: List[ActualHoursEntry]
    expected_revision: UUID | None = None


class ActualHoursResponse(ActualHoursRequest):
    """GET /actual-hours : les heures réelles, et les jours du mois où des heures
    sont saisies alors que le prévu est un arrêt ou une absence non travaillée
    (règle de `domain.conflits_arret`)."""

    jours_en_conflit: List[int] = Field(default_factory=list)
    expected_revision: UUID | None = Field(default=None, exclude=True)


class CalendarSaveRequest(BaseModel):
    year: int = Field(ge=2000, le=2100)
    month: int = Field(ge=1, le=12)
    # Champ obligatoire, null seulement si aucun mois n'existait à la lecture.
    expected_revision: UUID | None
    calendrier_prevu: list[PlannedCalendarEntry] | None = None
    calendrier_reel: list[ActualHoursEntry] | None = None
    recalculate_payroll: bool = False

    @model_validator(mode="after")
    def _has_entries(self):
        if self.calendrier_prevu is None and self.calendrier_reel is None:
            raise ValueError("Le prévu ou le réel à enregistrer est requis.")
        return self


class CalendarSnapshotResponse(BaseModel):
    year: int
    month: int
    revision: UUID | None
    busy: bool
    calendrier_prevu: list[PlannedCalendarEntryOut]
    calendrier_reel: list[ActualHoursEntry]
    jours_en_conflit: list[int] = Field(default_factory=list)


class CalendarSaveResponse(CalendarSnapshotResponse):
    revision: UUID
    warnings: list[dict[str, Any]] = Field(default_factory=list)
    payroll_recalculated: bool


class EffacerJoursRequest(BaseModel):
    """Corps de POST /actual-hours/effacer-jours : les jours du mois dont les
    heures, saisies sur un arrêt ou une absence, sont à effacer."""

    year: int = Field(ge=2000, le=2100)
    month: int = Field(ge=1, le=12)
    jours: List[int] = Field(min_length=1, max_length=31)

    @field_validator("jours")
    @classmethod
    def _jours_du_mois(cls, jours: List[int]) -> List[int]:
        if any(j < 1 or j > 31 for j in jours):
            raise ValueError("Chaque jour doit être compris entre 1 et 31.")
        return jours


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
    "ActualHoursResponse",
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
