# app/modules/cse/domain/enums.py
"""
Types énumérés CSE — alignés sur schemas/cse.py.
Migration : à terme, ces types peuvent être partagés avec schemas ou rester en domain.
"""
from typing import Literal

# Rôles et statuts (placeholders alignés sur l'existant)
ElectedMemberRole = Literal["titulaire", "suppleant", "secretaire", "tresorier", "autre"]
MeetingType = Literal["ordinaire", "extraordinaire", "cssct", "autre"]
MeetingStatus = Literal["a_venir", "en_cours", "terminee"]
RecordingStatus = Literal["not_started", "in_progress", "completed", "failed"]
ParticipantRole = Literal["participant", "observateur"]
BDESDocumentType = Literal["bdes", "pv", "autre"]
ElectionCycleStatus = Literal["in_progress", "completed"]
TimelineStepStatus = Literal["pending", "completed", "overdue"]
