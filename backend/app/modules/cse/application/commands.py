# app/modules/cse/application/commands.py
"""
Commandes CSE (écriture) — placeholders / wrappers vers services existants.
Migration : remplacer les appels aux services par l'utilisation des repositories et du domain.
"""
from typing import Any, List, Optional

# Délégation vers l'implémentation autonome (app.modules.cse.infrastructure)
def create_elected_member(company_id: str, data: Any, created_by: Optional[str] = None) -> Any:
    from app.modules.cse.infrastructure.cse_service_impl import create_elected_member as _create
    return _create(company_id, data, created_by)


def update_elected_member(member_id: str, data: Any, company_id: str) -> Any:
    from app.modules.cse.infrastructure.cse_service_impl import update_elected_member as _update
    return _update(member_id, data, company_id)


def create_meeting(company_id: str, data: Any, created_by: str) -> Any:
    from app.modules.cse.infrastructure.cse_service_impl import create_meeting as _create
    return _create(company_id, data, created_by)


def update_meeting(meeting_id: str, company_id: str, data: Any) -> Any:
    from app.modules.cse.infrastructure.cse_service_impl import update_meeting as _update
    return _update(meeting_id, company_id, data)


def add_participants(meeting_id: str, employee_ids: List[str]) -> List[Any]:
    from app.modules.cse.infrastructure.cse_service_impl import add_participants as _add
    return _add(meeting_id, employee_ids)


def remove_participant(meeting_id: str, employee_id: str) -> None:
    from app.modules.cse.infrastructure.cse_service_impl import remove_participant as _remove
    return _remove(meeting_id, employee_id)


def start_recording(meeting_id: str, company_id: str, consents: List[dict]) -> Any:
    from app.modules.cse.infrastructure.cse_service_impl import start_recording as _start
    return _start(meeting_id, company_id, consents)


def stop_recording(meeting_id: str, company_id: str) -> Any:
    from app.modules.cse.infrastructure.cse_service_impl import stop_recording as _stop
    return _stop(meeting_id, company_id)


def create_delegation_hour(company_id: str, employee_id: str, data: Any, created_by: str) -> Any:
    from app.modules.cse.infrastructure.cse_service_impl import create_delegation_hour as _create
    return _create(company_id, employee_id, data, created_by)


def upload_bdes_document(company_id: str, data: Any, published_by: str) -> Any:
    from app.modules.cse.infrastructure.cse_service_impl import upload_bdes_document as _upload
    return _upload(company_id, data, published_by)


def create_election_cycle(company_id: str, data: Any) -> Any:
    from app.modules.cse.infrastructure.cse_service_impl import create_election_cycle as _create
    return _create(company_id, data)


def process_recording(meeting_id: str) -> dict:
    from app.modules.cse.infrastructure.cse_ai_impl import process_recording as _process
    return _process(meeting_id)
