# app/modules/cse/api/router.py
"""
Router CSE — endpoints HTTP déléguant à la couche application uniquement.
Même préfixe, tags et comportement que api/routers/cse.py. Aucune logique métier dans le router.
"""
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form
from fastapi.responses import Response

from app.core.security import get_current_user
from app.modules.users.schemas.responses import User

from app.modules.cse.application import commands, queries
from app.modules.cse.application.service import (
    export_delegation_hours_file,
    export_elected_members_file,
    export_election_calendar_file,
    export_meetings_history_file,
    export_minutes_annual_file,
    get_meeting_minutes_path_or_raise,
)
from app.modules.cse.schemas import (
    BDESDocumentCreate,
    BDESDocumentRead,
    DelegationHourCreate,
    DelegationHourRead,
    DelegationQuotaRead,
    DelegationSummary,
    ElectionCycleCreate,
    ElectionCycleRead,
    ElectionAlert,
    ElectedMemberCreate,
    ElectedMemberRead,
    ElectedMemberListItem,
    ElectedMemberStatus,
    ElectedMemberUpdate,
    MandateAlert,
    MeetingCreate,
    MeetingListItem,
    MeetingParticipantAdd,
    MeetingParticipantRead,
    MeetingRead,
    MeetingUpdate,
    MeetingStatus,
    RecordingStart,
    RecordingStatusRead,
)

router = APIRouter(
    prefix="/api/cse",
    tags=["CSE & Dialogue Social"],
)


# ---------------------------------------------------------------------------
# Helpers HTTP (contexte, auth) — pas de logique métier
# ---------------------------------------------------------------------------

def _get_company_id(user: User) -> str:
    cid = user.active_company_id
    if not cid:
        raise HTTPException(status_code=400, detail="Aucune entreprise active sélectionnée.")
    return str(cid)


def _is_rh(user: User) -> bool:
    if user.is_super_admin:
        return True
    if not user.active_company_id:
        return False
    return user.has_rh_access_in_company(user.active_company_id)


def _require_rh(current_user: User) -> None:
    if not _is_rh(current_user):
        raise HTTPException(status_code=403, detail="Accès réservé aux RH.")


def _require_elected_or_rh(
    current_user: User, company_id: str, employee_id: Optional[str] = None
) -> None:
    if _is_rh(current_user):
        return
    user_employee_id = employee_id or str(current_user.id)
    if queries.is_elected_member(company_id, user_employee_id):
        return
    raise HTTPException(status_code=403, detail="Accès réservé aux élus CSE ou aux RH.")


def _check_meeting_access(current_user: User, meeting_id: str, company_id: str) -> None:
    if _is_rh(current_user):
        return
    _require_elected_or_rh(current_user, company_id)


def _consents_to_dict(consents) -> list:
    return [getattr(c, "model_dump", c.dict)() for c in consents]


# ---------------------------------------------------------------------------
# Élus CSE
# ---------------------------------------------------------------------------

@router.get("/elected-members", response_model=List[ElectedMemberListItem])
def list_elected_members(
    active_only: bool = Query(True),
    current_user: User = Depends(get_current_user),
):
    """Liste des élus CSE. RH uniquement."""
    _require_rh(current_user)
    company_id = _get_company_id(current_user)
    queries.check_module_active(company_id)
    return queries.get_elected_members(company_id, active_only=active_only)


@router.post("/elected-members", response_model=ElectedMemberRead, status_code=201)
def create_elected_member_endpoint(
    body: ElectedMemberCreate,
    current_user: User = Depends(get_current_user),
):
    """Crée un nouvel élu CSE. RH uniquement."""
    _require_rh(current_user)
    company_id = _get_company_id(current_user)
    queries.check_module_active(company_id)
    return commands.create_elected_member(
        company_id=company_id, data=body, created_by=str(current_user.id)
    )


@router.put("/elected-members/{member_id}", response_model=ElectedMemberRead)
def update_elected_member_endpoint(
    member_id: str,
    body: ElectedMemberUpdate,
    current_user: User = Depends(get_current_user),
):
    """Met à jour un élu CSE. RH uniquement."""
    _require_rh(current_user)
    company_id = _get_company_id(current_user)
    queries.check_module_active(company_id)
    return commands.update_elected_member(member_id, body, company_id)


@router.get("/elected-members/alerts", response_model=List[MandateAlert])
def get_mandate_alerts_endpoint(
    months_before: int = Query(3, ge=1, le=12),
    current_user: User = Depends(get_current_user),
):
    """Alertes de fin de mandat. RH uniquement."""
    _require_rh(current_user)
    company_id = _get_company_id(current_user)
    queries.check_module_active(company_id)
    return queries.get_mandate_alerts(company_id, months_before=months_before)


@router.get("/elected-members/me", response_model=ElectedMemberStatus)
def get_my_elected_status(
    current_user: User = Depends(get_current_user),
):
    """Statut élu de l'utilisateur connecté ou d'un employé (RH)."""
    company_id = _get_company_id(current_user)
    queries.check_module_active(company_id)
    employee_id = str(current_user.id)
    return queries.get_my_elected_status(company_id, employee_id)


# ---------------------------------------------------------------------------
# Réunions CSE
# ---------------------------------------------------------------------------

@router.get("/meetings", response_model=List[MeetingListItem])
def list_meetings(
    status: Optional[MeetingStatus] = Query(None),
    meeting_type: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
):
    """Liste des réunions CSE. RH : toutes, Élu : ses réunions uniquement."""
    company_id = _get_company_id(current_user)
    queries.check_module_active(company_id)
    if not _is_rh(current_user):
        _require_elected_or_rh(current_user, company_id)
    return queries.get_meetings(
        company_id=company_id,
        status=status,
        meeting_type=meeting_type,
        participant_id=None,
    )


@router.post("/meetings", response_model=MeetingRead, status_code=201)
def create_meeting_endpoint(
    body: MeetingCreate,
    current_user: User = Depends(get_current_user),
):
    """Crée une nouvelle réunion CSE. RH uniquement."""
    _require_rh(current_user)
    company_id = _get_company_id(current_user)
    queries.check_module_active(company_id)
    return commands.create_meeting(
        company_id=company_id, data=body, created_by=str(current_user.id)
    )


@router.get("/meetings/{meeting_id}", response_model=MeetingRead)
def get_meeting_endpoint(
    meeting_id: str,
    current_user: User = Depends(get_current_user),
):
    """Détail d'une réunion CSE. Vérification d'accès (participant ou RH)."""
    company_id = _get_company_id(current_user)
    queries.check_module_active(company_id)
    _check_meeting_access(current_user, meeting_id, company_id)
    return queries.get_meeting_by_id(meeting_id, company_id)


@router.put("/meetings/{meeting_id}", response_model=MeetingRead)
def update_meeting_endpoint(
    meeting_id: str,
    body: MeetingUpdate,
    current_user: User = Depends(get_current_user),
):
    """Met à jour une réunion CSE. RH uniquement."""
    _require_rh(current_user)
    company_id = _get_company_id(current_user)
    queries.check_module_active(company_id)
    return commands.update_meeting(meeting_id, company_id, body)


@router.post("/meetings/{meeting_id}/participants", response_model=List[MeetingParticipantRead])
def add_meeting_participants_endpoint(
    meeting_id: str,
    body: MeetingParticipantAdd,
    current_user: User = Depends(get_current_user),
):
    """Ajoute des participants à une réunion. RH uniquement."""
    _require_rh(current_user)
    company_id = _get_company_id(current_user)
    queries.check_module_active(company_id)
    return commands.add_participants(meeting_id, body.employee_ids)


@router.delete("/meetings/{meeting_id}/participants/{employee_id}")
def remove_meeting_participant_endpoint(
    meeting_id: str,
    employee_id: str,
    current_user: User = Depends(get_current_user),
):
    """Retire un participant d'une réunion. RH uniquement."""
    _require_rh(current_user)
    company_id = _get_company_id(current_user)
    queries.check_module_active(company_id)
    commands.remove_participant(meeting_id, employee_id)
    return {"message": "Participant retiré avec succès"}


@router.put("/meetings/{meeting_id}/status", response_model=MeetingRead)
def update_meeting_status_endpoint(
    meeting_id: str,
    status: MeetingStatus = Query(...),
    current_user: User = Depends(get_current_user),
):
    """Change le statut d'une réunion. RH uniquement."""
    _require_rh(current_user)
    company_id = _get_company_id(current_user)
    queries.check_module_active(company_id)
    return commands.update_meeting(meeting_id, company_id, MeetingUpdate(status=status))


# ---------------------------------------------------------------------------
# Enregistrements
# ---------------------------------------------------------------------------

@router.post("/meetings/{meeting_id}/recording/start", response_model=RecordingStatusRead)
def start_recording_endpoint(
    meeting_id: str,
    body: RecordingStart,
    current_user: User = Depends(get_current_user),
):
    """Démarre l'enregistrement d'une réunion avec consentements RGPD. RH uniquement."""
    _require_rh(current_user)
    company_id = _get_company_id(current_user)
    queries.check_module_active(company_id)
    return commands.start_recording(
        meeting_id=meeting_id,
        company_id=company_id,
        consents=_consents_to_dict(body.consents),
    )


@router.post("/meetings/{meeting_id}/recording/stop", response_model=RecordingStatusRead)
def stop_recording_endpoint(
    meeting_id: str,
    current_user: User = Depends(get_current_user),
):
    """Arrête l'enregistrement d'une réunion. RH uniquement."""
    _require_rh(current_user)
    company_id = _get_company_id(current_user)
    queries.check_module_active(company_id)
    return commands.stop_recording(meeting_id, company_id)


@router.get("/meetings/{meeting_id}/recording/status", response_model=RecordingStatusRead)
def get_recording_status_endpoint(
    meeting_id: str,
    current_user: User = Depends(get_current_user),
):
    """Statut d'un enregistrement. RH ou participant."""
    company_id = _get_company_id(current_user)
    queries.check_module_active(company_id)
    _check_meeting_access(current_user, meeting_id, company_id)
    return queries.get_recording_status(meeting_id)


@router.post("/meetings/{meeting_id}/recording/process")
def process_recording_endpoint(
    meeting_id: str,
    current_user: User = Depends(get_current_user),
):
    """Traite un enregistrement (transcription + synthèse IA). RH uniquement."""
    _require_rh(current_user)
    company_id = _get_company_id(current_user)
    queries.check_module_active(company_id)
    return commands.process_recording(meeting_id)


# ---------------------------------------------------------------------------
# PV et documents BDES
# ---------------------------------------------------------------------------

@router.get("/meetings/{meeting_id}/minutes")
def download_minutes(
    meeting_id: str,
    current_user: User = Depends(get_current_user),
):
    """Télécharge le PV d'une réunion. RH ou participant."""
    company_id = _get_company_id(current_user)
    queries.check_module_active(company_id)
    _check_meeting_access(current_user, meeting_id, company_id)
    pdf_path = get_meeting_minutes_path_or_raise(meeting_id, company_id)
    return {"pdf_path": pdf_path}


@router.get("/bdes-documents", response_model=List[BDESDocumentRead])
def list_bdes_documents(
    year: Optional[int] = Query(None),
    document_type: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
):
    """Liste des documents BDES. RH : toutes, Élu : visibles uniquement."""
    company_id = _get_company_id(current_user)
    queries.check_module_active(company_id)
    visible_to_elected_only = not _is_rh(current_user)
    if visible_to_elected_only:
        _require_elected_or_rh(current_user, company_id)
    return queries.get_bdes_documents(
        company_id=company_id,
        year=year,
        document_type=document_type,
        visible_to_elected_only=visible_to_elected_only,
    )


@router.post("/bdes-documents", response_model=BDESDocumentRead, status_code=201)
def upload_bdes_document_endpoint(
    title: str = Form(...),
    document_type: str = Form(...),
    year: Optional[int] = Form(None),
    is_visible_to_elected: bool = Form(True),
    description: Optional[str] = Form(None),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """Upload un document BDES. RH uniquement."""
    _require_rh(current_user)
    company_id = _get_company_id(current_user)
    queries.check_module_active(company_id)
    file_path = f"bdes/{company_id}/{file.filename}"
    data = BDESDocumentCreate(
        title=title,
        document_type=document_type,
        file_path=file_path,
        year=year,
        is_visible_to_elected=is_visible_to_elected,
        description=description,
    )
    return commands.upload_bdes_document(
        company_id=company_id, data=data, published_by=str(current_user.id)
    )


@router.get("/bdes-documents/{document_id}/download")
def download_bdes_document(
    document_id: str,
    current_user: User = Depends(get_current_user),
):
    """Télécharge un document BDES. RH ou élu (si visible)."""
    company_id = _get_company_id(current_user)
    queries.check_module_active(company_id)
    document = queries.get_bdes_document_by_id(document_id, company_id)
    if not _is_rh(current_user):
        if not document.is_visible_to_elected:
            raise HTTPException(status_code=403, detail="Document non accessible")
        _require_elected_or_rh(current_user, company_id)
    return {"download_url": document.file_path}


# ---------------------------------------------------------------------------
# Heures de délégation
# ---------------------------------------------------------------------------

@router.get("/delegation/quota", response_model=Optional[DelegationQuotaRead])
def get_delegation_quota_endpoint(
    employee_id: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
):
    """Récupère le quota mensuel d'heures de délégation. Élu : son quota, RH : quota d'un élu."""
    company_id = _get_company_id(current_user)
    queries.check_module_active(company_id)
    target_employee_id = (
        employee_id if (_is_rh(current_user) and employee_id) else str(current_user.id)
    )
    if not _is_rh(current_user):
        _require_elected_or_rh(current_user, company_id, target_employee_id)
    return queries.get_delegation_quota(company_id, target_employee_id)


@router.get("/delegation/hours", response_model=List[DelegationHourRead])
def get_delegation_hours_endpoint(
    employee_id: Optional[str] = Query(None),
    period_start: Optional[str] = Query(None),
    period_end: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
):
    """Récupère les heures de délégation. Élu : ses heures, RH : heures d'un élu."""
    company_id = _get_company_id(current_user)
    queries.check_module_active(company_id)
    target_employee_id = (
        employee_id if (_is_rh(current_user) and employee_id) else str(current_user.id)
    )
    if not _is_rh(current_user):
        _require_elected_or_rh(current_user, company_id, target_employee_id)
    start_date = datetime.fromisoformat(period_start).date() if period_start else None
    end_date = datetime.fromisoformat(period_end).date() if period_end else None
    return queries.get_delegation_hours(
        company_id, target_employee_id, start_date, end_date
    )


@router.post("/delegation/hours", response_model=DelegationHourRead, status_code=201)
def create_delegation_hour_endpoint(
    body: DelegationHourCreate,
    current_user: User = Depends(get_current_user),
):
    """Saisit une heure de délégation. Élu ou RH pour un élu."""
    company_id = _get_company_id(current_user)
    queries.check_module_active(company_id)
    target_employee_id = body.employee_id or str(current_user.id)
    if not _is_rh(current_user):
        if target_employee_id != str(current_user.id):
            raise HTTPException(
                status_code=403,
                detail="Vous ne pouvez saisir que vos propres heures",
            )
        _require_elected_or_rh(current_user, company_id, target_employee_id)
    return commands.create_delegation_hour(
        company_id=company_id,
        employee_id=target_employee_id,
        data=body,
        created_by=str(current_user.id),
    )


@router.get("/delegation/summary", response_model=List[DelegationSummary])
def get_delegation_summary_endpoint(
    period_start: str = Query(...),
    period_end: str = Query(...),
    current_user: User = Depends(get_current_user),
):
    """Récapitulatif des heures de délégation pour tous les élus. RH uniquement."""
    _require_rh(current_user)
    company_id = _get_company_id(current_user)
    queries.check_module_active(company_id)
    start_date = datetime.fromisoformat(period_start).date()
    end_date = datetime.fromisoformat(period_end).date()
    return queries.get_delegation_summary(company_id, start_date, end_date)


@router.get("/delegation/quotas", response_model=List[DelegationQuotaRead])
def list_delegation_quotas(
    current_user: User = Depends(get_current_user),
):
    """Liste des quotas par convention collective. RH uniquement."""
    _require_rh(current_user)
    company_id = _get_company_id(current_user)
    queries.check_module_active(company_id)
    return queries.list_delegation_quotas(company_id)


# ---------------------------------------------------------------------------
# Calendrier électoral
# ---------------------------------------------------------------------------

@router.get("/election-cycles", response_model=List[ElectionCycleRead])
def list_election_cycles(
    current_user: User = Depends(get_current_user),
):
    """Liste des cycles électoraux. RH uniquement."""
    _require_rh(current_user)
    company_id = _get_company_id(current_user)
    queries.check_module_active(company_id)
    return queries.get_election_cycles(company_id)


@router.post("/election-cycles", response_model=ElectionCycleRead, status_code=201)
def create_election_cycle_endpoint(
    body: ElectionCycleCreate,
    current_user: User = Depends(get_current_user),
):
    """Crée un cycle électoral. RH uniquement."""
    _require_rh(current_user)
    company_id = _get_company_id(current_user)
    queries.check_module_active(company_id)
    return commands.create_election_cycle(company_id, body)


@router.get("/election-cycles/alerts", response_model=List[ElectionAlert])
def get_election_alerts_endpoint(
    current_user: User = Depends(get_current_user),
):
    """Alertes électorales (J-180, J-90, J-30). RH uniquement."""
    _require_rh(current_user)
    company_id = _get_company_id(current_user)
    queries.check_module_active(company_id)
    return queries.get_election_alerts(company_id)


@router.get("/election-cycles/{cycle_id}", response_model=ElectionCycleRead)
def get_election_cycle_endpoint(
    cycle_id: str,
    current_user: User = Depends(get_current_user),
):
    """Détail d'un cycle électoral. RH uniquement."""
    _require_rh(current_user)
    company_id = _get_company_id(current_user)
    queries.check_module_active(company_id)
    return queries.get_election_cycle_by_id(cycle_id, company_id)


# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------

@router.get("/exports/elected-members")
def export_elected_members(
    current_user: User = Depends(get_current_user),
):
    """Export Excel de la base des élus. RH uniquement."""
    _require_rh(current_user)
    company_id = _get_company_id(current_user)
    queries.check_module_active(company_id)
    out = export_elected_members_file(company_id)
    return Response(
        content=out.content,
        media_type=out.media_type,
        headers={"Content-Disposition": f'attachment; filename="{out.filename}"'},
    )


@router.get("/exports/delegation-hours")
def export_delegation_hours(
    period_start: Optional[str] = Query(None),
    period_end: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
):
    """Export Excel des heures de délégation. RH uniquement."""
    _require_rh(current_user)
    company_id = _get_company_id(current_user)
    queries.check_module_active(company_id)
    out = export_delegation_hours_file(company_id, period_start, period_end)
    return Response(
        content=out.content,
        media_type=out.media_type,
        headers={"Content-Disposition": f'attachment; filename="{out.filename}"'},
    )


@router.get("/exports/meetings-history")
def export_meetings_history(
    period_start: Optional[str] = Query(None),
    period_end: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
):
    """Export Excel de l'historique des réunions. RH uniquement."""
    _require_rh(current_user)
    company_id = _get_company_id(current_user)
    queries.check_module_active(company_id)
    out = export_meetings_history_file(company_id)
    return Response(
        content=out.content,
        media_type=out.media_type,
        headers={"Content-Disposition": f'attachment; filename="{out.filename}"'},
    )


@router.get("/exports/minutes-annual")
def export_minutes_annual(
    year: int = Query(...),
    current_user: User = Depends(get_current_user),
):
    """Export PDF des PV annuels. RH uniquement."""
    _require_rh(current_user)
    company_id = _get_company_id(current_user)
    queries.check_module_active(company_id)
    out = export_minutes_annual_file(company_id, year)
    return Response(
        content=out.content,
        media_type=out.media_type,
        headers={"Content-Disposition": f'attachment; filename="{out.filename}"'},
    )


@router.get("/exports/election-calendar")
def export_election_calendar(
    cycle_id: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
):
    """Export PDF du calendrier des obligations sociales. RH uniquement."""
    _require_rh(current_user)
    company_id = _get_company_id(current_user)
    queries.check_module_active(company_id)
    out = export_election_calendar_file(company_id, cycle_id)
    return Response(
        content=out.content,
        media_type=out.media_type,
        headers={"Content-Disposition": f'attachment; filename="{out.filename}"'},
    )
