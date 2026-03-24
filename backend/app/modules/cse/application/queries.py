# app/modules/cse/application/queries.py
"""
Queries CSE (lecture) — logique applicative via domain/infrastructure.
Utilise les repositories ; check_module_active reste délégué au service legacy.
"""
from datetime import date
from typing import Any, List, Optional

from app.modules.cse.infrastructure.repository import (
    bdes_document_repository,
    delegation_repository,
    elected_member_repository,
    election_cycle_repository,
    meeting_repository,
    recording_repository,
)
from app.modules.cse.schemas import DelegationQuotaRead, ElectedMemberStatus


def check_module_active(company_id: str) -> None:
    """Vérification module actif (no-op : toutes les entreprises ont accès)."""
    return


def get_elected_members(company_id: str, active_only: bool = True) -> List[Any]:
    return elected_member_repository.list_by_company(company_id, active_only=active_only)


def get_elected_member_by_id(member_id: str) -> Any:
    return elected_member_repository.get_by_id(member_id)


def get_elected_member_by_employee(company_id: str, employee_id: str) -> Optional[Any]:
    return elected_member_repository.get_by_employee(company_id, employee_id)


def get_mandate_alerts(company_id: str, months_before: int = 3) -> List[Any]:
    return elected_member_repository.get_mandate_alerts(company_id, months_before=months_before)


def get_meetings(
    company_id: str,
    status: Optional[Any] = None,
    meeting_type: Optional[str] = None,
    participant_id: Optional[str] = None,
) -> List[Any]:
    return meeting_repository.list_by_company(
        company_id,
        status=status,
        meeting_type=meeting_type,
        participant_id=participant_id,
    )


def get_meeting_by_id(meeting_id: str, company_id: str) -> Any:
    return meeting_repository.get_by_id(meeting_id, company_id)


def get_meeting_participants(meeting_id: str) -> List[Any]:
    return meeting_repository.get_participants(meeting_id)


def get_recording_status(meeting_id: str) -> Any:
    return recording_repository.get_status(meeting_id)


def get_delegation_quota(company_id: str, employee_id: str) -> Optional[Any]:
    return delegation_repository.get_quota(company_id, employee_id)


def get_delegation_hours(
    company_id: str,
    employee_id: str,
    period_start: Optional[date] = None,
    period_end: Optional[date] = None,
) -> List[Any]:
    return delegation_repository.list_hours(
        company_id, employee_id, period_start, period_end
    )


def get_delegation_summary(
    company_id: str, period_start: date, period_end: date
) -> List[Any]:
    return delegation_repository.get_summary(company_id, period_start, period_end)


def get_bdes_documents(
    company_id: str,
    year: Optional[int] = None,
    document_type: Optional[str] = None,
    visible_to_elected_only: bool = False,
) -> List[Any]:
    return bdes_document_repository.list_by_company(
        company_id,
        year=year,
        document_type=document_type,
        visible_to_elected_only=visible_to_elected_only,
    )


def get_bdes_document_by_id(document_id: str, company_id: str) -> Any:
    return bdes_document_repository.get_by_id(document_id, company_id)


def get_election_cycles(company_id: str) -> List[Any]:
    return election_cycle_repository.list_by_company(company_id)


def get_election_cycle_by_id(cycle_id: str, company_id: str) -> Any:
    return election_cycle_repository.get_by_id(cycle_id, company_id)


def get_election_alerts(company_id: str) -> List[Any]:
    return election_cycle_repository.get_election_alerts(company_id)


def is_elected_member(company_id: str, employee_id: str) -> bool:
    return elected_member_repository.is_elected(company_id, employee_id)


def get_my_elected_status(company_id: str, employee_id: str) -> ElectedMemberStatus:
    """Statut élu d'un employé : is_elected, current_mandate, role."""
    check_module_active(company_id)
    mandate = get_elected_member_by_employee(company_id, employee_id)
    return ElectedMemberStatus(
        is_elected=mandate is not None,
        current_mandate=mandate,
        role=mandate.role if mandate else None,
    )


def list_delegation_quotas(company_id: str) -> List[DelegationQuotaRead]:
    """Liste des quotas de délégation par convention collective."""
    check_module_active(company_id)
    return delegation_repository.list_quotas(company_id)


def get_meeting_minutes_path(meeting_id: str, company_id: str) -> Optional[str]:
    """Chemin du PV d'une réunion (table cse_meeting_recordings)."""
    check_module_active(company_id)
    return recording_repository.get_minutes_path(meeting_id, company_id)
