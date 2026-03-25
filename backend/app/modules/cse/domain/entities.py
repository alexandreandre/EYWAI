# app/modules/cse/domain/entities.py
"""
Entités CSE — placeholders pour la couche domain.
Migration : remplacer par des entités riches (dates, invariants) une fois l'infra en place.
Référence : cse_elected_members, cse_meetings, cse_meeting_participants,
cse_meeting_recordings, cse_delegation_quotas, cse_delegation_hours,
cse_bdes_documents, cse_election_cycles, cse_election_timeline.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class ElectedMemberId:
    """Identifiant d'un élu CSE."""
    value: str


@dataclass(frozen=True)
class MeetingId:
    """Identifiant d'une réunion CSE."""
    value: str


# Placeholders minimaux — à enrichir lors de la migration
# ElectedMember, Meeting, MeetingParticipant, Recording, DelegationHour,
# DelegationQuota, BDESDocument, ElectionCycle, ElectionTimelineStep
