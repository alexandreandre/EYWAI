# app/modules/cse/infrastructure/repository.py
"""
Implémentations des repositories CSE — délégation vers services existants + queries/mappers locaux.
Comportement strictement identique à l'existant.
"""
from datetime import date
from typing import Any, List, Optional

from app.modules.cse.domain.interfaces import (
    IBDESDocumentRepository,
    IElectedMemberRepository,
    IElectionCycleRepository,
    IDelegationRepository,
    IMeetingRepository,
    IRecordingRepository,
)
from app.modules.cse.infrastructure.mappers import map_delegation_quota_row_to_read
from app.modules.cse.infrastructure.queries import (
    fetch_delegation_quotas_for_company,
    fetch_meeting_minutes_path,
)


class ElectedMemberRepository(IElectedMemberRepository):
    """Délègue à services.cse_service."""

    def list_by_company(self, company_id: str, active_only: bool = True) -> List[Any]:
        from app.modules.cse.infrastructure.cse_service_impl import get_elected_members
        return get_elected_members(company_id, active_only=active_only)

    def get_by_id(self, member_id: str) -> Any:
        from app.modules.cse.infrastructure.cse_service_impl import get_elected_member_by_id
        return get_elected_member_by_id(member_id)

    def get_by_employee(self, company_id: str, employee_id: str) -> Optional[Any]:
        from app.modules.cse.infrastructure.cse_service_impl import get_elected_member_by_employee
        return get_elected_member_by_employee(company_id, employee_id)

    def is_elected(self, company_id: str, employee_id: str) -> bool:
        from app.modules.cse.infrastructure.cse_service_impl import _is_elected_member
        return _is_elected_member(company_id, employee_id)

    def get_mandate_alerts(self, company_id: str, months_before: int = 3) -> List[Any]:
        from app.modules.cse.infrastructure.cse_service_impl import get_mandate_alerts
        return get_mandate_alerts(company_id, months_before=months_before)


class MeetingRepository(IMeetingRepository):
    """Délègue à services.cse_service."""

    def list_by_company(
        self,
        company_id: str,
        status: Optional[str] = None,
        meeting_type: Optional[str] = None,
        participant_id: Optional[str] = None,
    ) -> List[Any]:
        from app.modules.cse.infrastructure.cse_service_impl import get_meetings
        return get_meetings(
            company_id,
            status=status,
            meeting_type=meeting_type,
            participant_id=participant_id,
        )

    def get_by_id(self, meeting_id: str, company_id: str) -> Any:
        from app.modules.cse.infrastructure.cse_service_impl import get_meeting_by_id
        return get_meeting_by_id(meeting_id, company_id)

    def get_participants(self, meeting_id: str) -> List[Any]:
        from app.modules.cse.infrastructure.cse_service_impl import get_meeting_participants
        return get_meeting_participants(meeting_id)


class RecordingRepository(IRecordingRepository):
    """Délègue à services.cse_service pour get_status ; queries locales pour get_minutes_path."""

    def get_status(self, meeting_id: str) -> Any:
        from app.modules.cse.infrastructure.cse_service_impl import get_recording_status
        return get_recording_status(meeting_id)

    def get_minutes_path(self, meeting_id: str, company_id: str) -> Optional[str]:
        return fetch_meeting_minutes_path(meeting_id)


class DelegationRepository(IDelegationRepository):
    """Délègue à services.cse_service ; list_quotas via queries + mapper."""

    def get_quota(self, company_id: str, employee_id: str) -> Optional[Any]:
        from app.modules.cse.infrastructure.cse_service_impl import get_delegation_quota
        return get_delegation_quota(company_id, employee_id)

    def list_quotas(self, company_id: str) -> List[Any]:
        rows = fetch_delegation_quotas_for_company(company_id)
        return [map_delegation_quota_row_to_read(row) for row in rows]

    def list_hours(
        self,
        company_id: str,
        employee_id: str,
        period_start: Optional[date] = None,
        period_end: Optional[date] = None,
    ) -> List[Any]:
        from app.modules.cse.infrastructure.cse_service_impl import get_delegation_hours
        return get_delegation_hours(company_id, employee_id, period_start, period_end)

    def get_summary(
        self, company_id: str, period_start: Any, period_end: Any
    ) -> List[Any]:
        from app.modules.cse.infrastructure.cse_service_impl import get_delegation_summary
        return get_delegation_summary(company_id, period_start, period_end)


class BDESDocumentRepository(IBDESDocumentRepository):
    """Délègue à services.cse_service."""

    def list_by_company(
        self,
        company_id: str,
        year: Optional[int] = None,
        document_type: Optional[str] = None,
        visible_to_elected_only: bool = False,
    ) -> List[Any]:
        from app.modules.cse.infrastructure.cse_service_impl import get_bdes_documents
        return get_bdes_documents(
            company_id,
            year=year,
            document_type=document_type,
            visible_to_elected_only=visible_to_elected_only,
        )

    def get_by_id(self, document_id: str, company_id: str) -> Any:
        from app.modules.cse.infrastructure.cse_service_impl import get_bdes_document_by_id
        return get_bdes_document_by_id(document_id, company_id)


class ElectionCycleRepository(IElectionCycleRepository):
    """Délègue à services.cse_service."""

    def list_by_company(self, company_id: str) -> List[Any]:
        from app.modules.cse.infrastructure.cse_service_impl import get_election_cycles
        return get_election_cycles(company_id)

    def get_by_id(self, cycle_id: str, company_id: str) -> Any:
        from app.modules.cse.infrastructure.cse_service_impl import get_election_cycle_by_id
        return get_election_cycle_by_id(cycle_id, company_id)

    def get_election_alerts(self, company_id: str) -> List[Any]:
        from app.modules.cse.infrastructure.cse_service_impl import get_election_alerts
        return get_election_alerts(company_id)


# Instances partagées pour l'application
elected_member_repository: IElectedMemberRepository = ElectedMemberRepository()
meeting_repository: IMeetingRepository = MeetingRepository()
recording_repository: IRecordingRepository = RecordingRepository()
delegation_repository: IDelegationRepository = DelegationRepository()
bdes_document_repository: IBDESDocumentRepository = BDESDocumentRepository()
election_cycle_repository: IElectionCycleRepository = ElectionCycleRepository()
