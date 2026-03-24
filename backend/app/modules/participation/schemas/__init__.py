"""
Schémas API du module participation (Participation & Intéressement).

Contrats requêtes/réponses alignés sur le legacy pour compatibilité frontend.
"""
from app.modules.participation.schemas.requests import ParticipationSimulationCreate
from app.modules.participation.schemas.responses import (
    EmployeeDataResponse,
    EmployeeParticipationDataItem,
    ParticipationSimulationListItem,
    ParticipationSimulationResponse,
)

__all__ = [
    "ParticipationSimulationCreate",
    "ParticipationSimulationResponse",
    "ParticipationSimulationListItem",
    "EmployeeParticipationDataItem",
    "EmployeeDataResponse",
]
