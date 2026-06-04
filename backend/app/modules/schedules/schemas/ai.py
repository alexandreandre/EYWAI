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

from typing import List, Literal, Optional

from pydantic import BaseModel, Field

DayNature = Literal["prevu", "reel"]


class RosterEmployee(BaseModel):
    """Employé candidat fourni par le front pour la résolution nom -> id."""

    id: str
    first_name: str
    last_name: str


class ParseInstructionRequest(BaseModel):
    """Body POST /api/schedules/assisted-fill/parse-text."""

    year: int
    month: int
    instruction: str = Field(..., min_length=1)
    employees: List[RosterEmployee] = Field(default_factory=list)


class AiDayEntry(BaseModel):
    """Une journée proposée par l'IA pour un employé.

    `nature` indique s'il s'agit d'heures prévues (« prevu ») ou faites (« reel »).
    """

    jour: int
    heures: Optional[float] = None
    type: str = "travail"
    nature: DayNature = "reel"


class AiEmployeeProposal(BaseModel):
    """Proposition pour un employé : résolution + jours détectés."""

    raw_name: str
    employee_id: Optional[str] = None
    matched_name: Optional[str] = None
    match_confidence: Literal["high", "medium", "none"] = "none"
    days: List[AiDayEntry] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class AiCalendarProposalResponse(BaseModel):
    """Proposition complète renvoyée au front (jamais écrite directement)."""

    year: int
    month: int
    source: str
    employees: List[AiEmployeeProposal] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


__all__ = [
    "AiCalendarProposalResponse",
    "AiDayEntry",
    "AiEmployeeProposal",
    "DayNature",
    "ParseInstructionRequest",
    "RosterEmployee",
]
